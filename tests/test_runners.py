import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/jfactory/scripts/runners.py'

# Records every call and keeps containers in a JSON file: {name: {"state": ..., "repo": ..., "jit": ...}}.
FAKE_DOCKER = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
state = Path(os.environ['FAKE_STATE'])
args = sys.argv[1:]
with open(state / 'docker.log', 'a') as log:
    log.write(json.dumps(args) + '\n')
path = state / 'containers.json'
boxes = json.loads(path.read_text()) if path.exists() else {}
def save():
    path.write_text(json.dumps(boxes))
if args[:2] == ['image', 'inspect']:
    sys.exit(0 if (state / 'image').exists() else 1)
if args[0] == 'build':
    (state / 'image').write_text('built')
elif args[0] == 'ps':
    repo = next(a for a in args if a.startswith('label=')).split('=', 2)[2]
    for name, box in boxes.items():
        if box['repo'] == repo:
            print(f"{name}\t{box['state']}")
elif args[0] == 'create':
    if os.environ.get('FAKE_DOCKER_FAIL'):
        print('no space left on device', file=sys.stderr)
        sys.exit(1)
    name = args[args.index('--name') + 1]
    boxes[name] = {'state': 'created', 'repo': args[args.index('--label') + 1].split('=', 1)[1]}
    save()
elif args[0] == 'cp':
    name = args[2].split(':')[0]
    boxes[name]['jit'] = Path(args[1]).read_text()
    save()
elif args[0] == 'start':
    boxes[args[1]]['state'] = 'running'
    save()
elif args[0] == 'rm':
    boxes.pop(args[-1], None)
    save()
'''

# Runners come from runners.json: [{"id", "name", "status", "busy"}]; deletions are logged.
FAKE_GH = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
state = Path(os.environ['FAKE_STATE'])
args = sys.argv[1:]
with open(state / 'gh.log', 'a') as log:
    log.write(json.dumps(args) + '\n')
if os.environ.get('FAKE_GH_FORBIDDEN') and args[:1] == ['api']:
    print('{"message":"Resource not accessible by integration","status":"403"}', file=sys.stderr)
    sys.exit(1)
runners = json.loads((state / 'runners.json').read_text()) if (state / 'runners.json').exists() else []
if args[:2] == ['repo', 'view']:
    print('acme/shop')
elif 'generate-jitconfig' in ' '.join(args):
    name = next(a for a in args if a.startswith('name=')).split('=', 1)[1]
    print('jit-for-' + name)
elif args[:3] == ['api', '-X', 'DELETE']:
    pass
elif args[:1] == ['api'] and args[1].endswith('/actions/runners'):
    if '--paginate' in args:
        for r in runners:
            print(f"{r['id']}\t{r['name']}\t{r['status']}\t{str(r['busy']).lower()}")
    else:
        print(len(runners))
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
        self.env = {**os.environ, 'PATH': f'{bin_dir}:{os.environ["PATH"]}', 'FAKE_STATE': str(self.state),
                    'JFACTORY_RUNNER_STATE': str(self.state / 'runner-state')}
        (self.state / 'runner-state').mkdir()
        self.config = self.state / 'runner-state' / 'acme__shop.json'

    def tearDown(self):
        pid_file = self.state / 'runner-state' / 'acme__shop.pid'
        if pid_file.exists():
            try:
                os.kill(int(pid_file.read_text()), 15)
            except (OSError, ValueError):
                pass
        self.tmp.cleanup()

    def cli(self, *args, code=0, **env):
        result = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                                env={**self.env, **env}, timeout=60)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def log(self, name):
        path = self.state / name
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def containers(self):
        path = self.state / 'containers.json'
        return json.loads(path.read_text()) if path.exists() else {}

    def write_config(self, count=2):
        self.config.write_text(json.dumps({'count': count, 'labels': ['jfactory', 'gpu'], 'prefix': 'jfactory-shop-box',
                                           'cpus': None, 'memory': '6g', 'shm_size': '2g'}))

    def test_serve_keeps_count_single_use_runners_ready_with_configs_copied_in_not_passed(self):
        self.write_config(count=2)
        self.cli('serve', '--repo', 'acme/shop', '--once')
        boxes = self.containers()
        self.assertEqual(len(boxes), 2)
        for name, box in boxes.items():
            self.assertTrue(name.startswith('jfactory-shop-box-'))
            self.assertEqual(box['state'], 'running')
            self.assertEqual(box['jit'], f'jit-for-{name}')
        for args in self.log('docker.log'):
            self.assertFalse(any('jit-for-' in a for a in args), args)
        create = next(a for a in self.log('docker.log') if a[0] == 'create')
        self.assertIn('--rm', create)
        self.assertEqual(create[create.index('--memory') + 1], '6g')
        jit = next(a for a in self.log('gh.log') if 'generate-jitconfig' in ' '.join(a))
        self.assertEqual([a for a in jit if a.startswith('labels[]=')],
                         ['labels[]=self-hosted', 'labels[]=jfactory', 'labels[]=gpu'])
        # A finished job's container deletes itself; the next pass replaces only what is missing.
        boxes.pop(next(iter(boxes)))
        (self.state / 'containers.json').write_text(json.dumps(boxes))
        self.cli('serve', '--repo', 'acme/shop', '--once')
        self.assertEqual(len(self.containers()), 2)
        self.assertEqual(sum(a[0] == 'create' for a in self.log('docker.log')), 3)

    def test_serve_reports_docker_and_github_failures_and_keeps_going(self):
        self.write_config(count=1)
        out = self.cli('serve', '--repo', 'acme/shop', '--once', FAKE_DOCKER_FAIL='1')
        self.assertIn('no space left on device', out)
        out = self.cli('serve', '--repo', 'acme/shop', '--once', FAKE_GH_FORBIDDEN='1')
        self.assertIn('Administration: read and write', out)
        self.assertEqual(self.containers(), {})

    def test_up_refuses_a_token_that_cannot_administer_runners_before_starting_anything(self):
        out = self.cli('up', '--repo', 'acme/shop', '--count', '1', code=1, FAKE_GH_FORBIDDEN='1')
        self.assertIn('Administration: read and write', out)
        self.assertFalse((self.state / 'runner-state' / 'acme__shop.pid').exists())
        self.assertIn('at least 1', self.cli('up', '--repo', 'acme/shop', '--count', '0', code=1))
        self.assertIn('pass --repo', self.cli('status', '--repo', 'not a repo', code=1))

    def test_up_starts_a_supervisor_that_down_stops(self):
        out = self.cli('up', '--repo', 'acme/shop', '--count', '1', '--host', 'Box')
        self.assertIn('JFACTORY_RUNNER=["self-hosted", "jfactory"]', out)
        pid = int((self.state / 'runner-state' / 'acme__shop.pid').read_text())
        for _ in range(50):
            if self.containers():
                break
            time.sleep(0.1)
        self.assertEqual(len(self.containers()), 1)
        self.assertIn(f'running, pid {pid}', self.cli('status', '--repo', 'acme/shop'))
        self.cli('down', '--repo', 'acme/shop', '--wait', '0')
        time.sleep(0.5)
        status = Path(f'/proc/{pid}/status')
        self.assertTrue(not status.exists() or '\nState:\tZ' in status.read_text(), 'supervisor still running')

    def test_down_leaves_busy_runners_unless_forced_and_reports_what_stayed(self):
        self.write_config()
        (self.state / 'containers.json').write_text(json.dumps({
            'jfactory-shop-box-aaa': {'state': 'running', 'repo': 'acme/shop'},
            'jfactory-shop-box-bbb': {'state': 'running', 'repo': 'acme/shop'},
            'jfactory-blog-box-ccc': {'state': 'running', 'repo': 'acme/blog'},
        }))
        (self.state / 'runners.json').write_text(json.dumps([
            {'id': 1, 'name': 'jfactory-shop-box-aaa', 'status': 'online', 'busy': True},
            {'id': 2, 'name': 'jfactory-shop-box-bbb', 'status': 'online', 'busy': False},
            {'id': 3, 'name': 'jfactory-shop-box-old', 'status': 'offline', 'busy': False},
            {'id': 4, 'name': 'someone-else', 'status': 'online', 'busy': False},
        ]))
        out = self.cli('down', '--repo', 'acme/shop', '--wait', '0', code=1)
        self.assertIn('jfactory-shop-box-aaa (still running a job', out)
        self.assertEqual(sorted(self.containers()), ['jfactory-blog-box-ccc', 'jfactory-shop-box-aaa'])
        deleted = [a[3] for a in self.log('gh.log') if a[:3] == ['api', '-X', 'DELETE']]
        self.assertEqual(deleted, ['repos/acme/shop/actions/runners/2', 'repos/acme/shop/actions/runners/3'])
        self.cli('down', '--repo', 'acme/shop', '--force')
        self.assertEqual(list(self.containers()), ['jfactory-blog-box-ccc'])

    def test_down_fails_loudly_when_github_refuses_removal(self):
        self.write_config()
        (self.state / 'runners.json').write_text(json.dumps([
            {'id': 3, 'name': 'jfactory-shop-box-old', 'status': 'offline', 'busy': False}]))
        # Listing works but deletion is refused: simulate by making gh fail only on DELETE.
        gh = self.state / 'bin' / 'gh'
        gh.write_text(gh.read_text().replace("elif args[:3] == ['api', '-X', 'DELETE']:\n    pass",
                                             "elif args[:3] == ['api', '-X', 'DELETE']:\n    sys.exit(1)"))
        out = self.cli('down', '--repo', 'acme/shop', '--wait', '0', code=1)
        self.assertIn('GitHub refused removal', out)


if __name__ == '__main__':
    unittest.main()
