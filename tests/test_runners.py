import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/jfactory/scripts/runners.py'

# Records every call and keeps containers in a JSON file: {name: {"state": ..., "repo": ...}}.
FAKE_DOCKER = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
state = Path(os.environ['FAKE_STATE'])
args = sys.argv[1:]
with open(state / 'docker.log', 'a') as log:
    log.write(json.dumps({'args': args, 'token': os.environ.get('RUNNER_TOKEN'),
                          'remove': os.environ.get('RUNNER_REMOVE_TOKEN')}) + '\n')
path = state / 'containers.json'
boxes = json.loads(path.read_text()) if path.exists() else {}
def save():
    path.write_text(json.dumps(boxes))
if args[:2] == ['image', 'inspect']:
    sys.exit(0 if (state / 'image').exists() else 1)
if args[0] == 'build':
    (state / 'image').write_text('built')
elif args[0] == 'ps':
    for name, box in boxes.items():
        print(f"{name}\t{box['state']}\t{box['repo']}")
elif args[0] == 'run':
    name = args[args.index('--name') + 1]
    label = args[args.index('--label') + 1]
    boxes[name] = {'state': 'running', 'repo': label.split('=', 1)[1]}
    save()
elif args[0] == 'start':
    boxes[args[1]]['state'] = 'running'
    save()
elif args[0] == 'rm':
    boxes.pop(args[-1], None)
    save()
'''

FAKE_GH = r'''#!/usr/bin/env python3
import os, sys
args = sys.argv[1:]
if os.environ.get('FAKE_GH_FORBIDDEN') and args[:3] == ['api', '-X', 'POST']:
    print('{"message":"Resource not accessible by integration","status":"403"}', file=sys.stderr)
    sys.exit(1)
if args[:3] == ['api', '-X', 'POST']:
    print('tok-' + args[3].rsplit('/', 1)[1])
elif args[:2] == ['repo', 'view']:
    print('acme/shop')
elif args[:1] == ['api']:
    print('')
'''


class RunnersTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name)
        bin_dir = self.state / 'bin'
        bin_dir.mkdir()
        for name, body in (('docker', FAKE_DOCKER), ('gh', FAKE_GH)):
            (bin_dir / name).write_text(body)
            (bin_dir / name).chmod(0o755)
        self.env = {**os.environ, 'PATH': f'{bin_dir}:{os.environ["PATH"]}', 'FAKE_STATE': str(self.state)}

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *args, code=0, **env):
        result = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                                env={**self.env, **env})
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def calls(self):
        log = self.state / 'docker.log'
        return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []

    def containers(self):
        path = self.state / 'containers.json'
        return json.loads(path.read_text()) if path.exists() else {}

    def test_up_builds_once_and_registers_each_runner_with_the_token_kept_off_the_command_line(self):
        out = self.cli('up', '--repo', 'acme/shop', '--count', '2', '--host', 'Build.Box', '--labels', 'gpu,jfactory')
        self.assertIn('2 started', out)
        self.assertIn('JFACTORY_RUNNER=["self-hosted", "jfactory"]', out)
        runs = [c for c in self.calls() if c['args'][0] == 'run']
        self.assertEqual([r['args'][r['args'].index('--name') + 1] for r in runs],
                         ['jfactory-runner-shop-build-box-1', 'jfactory-runner-shop-build-box-2'])
        for r in runs:
            self.assertEqual(r['token'], 'tok-registration-token')
            self.assertNotIn('tok-registration-token', ' '.join(r['args']))
            self.assertIn('RUNNER_LABELS=jfactory,gpu', r['args'])
            self.assertIn('unless-stopped', r['args'])
        self.assertEqual(sum(c['args'][0] == 'build' for c in self.calls()), 1)
        # A second run reuses the image and the registered containers, restarting a stopped one.
        boxes = self.containers()
        boxes['jfactory-runner-shop-build-box-2']['state'] = 'exited'
        (self.state / 'containers.json').write_text(json.dumps(boxes))
        out = self.cli('up', '--repo', 'acme/shop', '--count', '2', '--host', 'Build.Box')
        self.assertIn('0 started, 2 already present', out)
        self.assertEqual(sum(c['args'][0] == 'build' for c in self.calls()), 1)
        self.assertEqual(sum(c['args'][0] == 'run' for c in self.calls()), 2)
        self.assertEqual(self.containers()['jfactory-runner-shop-build-box-2']['state'], 'running')

    def test_up_explains_a_token_that_cannot_administer_runners(self):
        out = self.cli('up', '--repo', 'acme/shop', '--count', '1', code=1, FAKE_GH_FORBIDDEN='1')
        self.assertIn('Administration: read and write', out)
        self.assertFalse(any(c['args'][0] == 'run' for c in self.calls()))

    def test_down_unregisters_and_removes_only_this_repositorys_runners(self):
        (self.state / 'containers.json').write_text(json.dumps({
            'jfactory-runner-shop-a-1': {'state': 'running', 'repo': 'acme/shop'},
            'jfactory-runner-blog-a-1': {'state': 'running', 'repo': 'acme/blog'},
        }))
        out = self.cli('down', '--repo', 'acme/shop')
        self.assertIn('Removed 1 runner(s)', out)
        self.assertEqual(list(self.containers()), ['jfactory-runner-blog-a-1'])
        removes = [c for c in self.calls() if c['args'][0] == 'exec']
        self.assertEqual(len(removes), 1)
        self.assertEqual(removes[0]['remove'], 'tok-remove-token')
        self.assertNotIn('tok-remove-token', ' '.join(removes[0]['args']))

    def test_down_still_removes_containers_when_github_refuses_the_removal_token(self):
        (self.state / 'containers.json').write_text(json.dumps({
            'jfactory-runner-shop-a-1': {'state': 'exited', 'repo': 'acme/shop'}}))
        out = self.cli('down', '--repo', 'acme/shop', FAKE_GH_FORBIDDEN='1')
        self.assertIn('stays listed on GitHub', out)
        self.assertEqual(self.containers(), {})

    def test_refuses_a_count_below_one_and_an_unclear_repository(self):
        self.assertIn('at least 1', self.cli('up', '--repo', 'acme/shop', '--count', '0', code=1))
        self.assertIn('pass --repo', self.cli('status', '--repo', 'not a repo', code=1))


if __name__ == '__main__':
    unittest.main()
