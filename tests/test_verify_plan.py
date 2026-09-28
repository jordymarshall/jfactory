import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills' / 'jfactory' / 'scripts' / 'verify_plan.py'
FAKE = ROOT / 'tests' / 'fakes' / 'fake_cli.py'
sys.path.insert(0, str(SCRIPT.parent))
import verify_plan  # noqa: E402

CONFIG = {
    'static': ['docs/**', '**/*.md'],
    'static_suites': ['static'],
    'always_suites': ['unit'],
    'full_suites': ['unit', 'browser'],
    'features': {
        'briefs': {'paths': ['app/briefs/**'], 'recipe': 'verify/briefs.md', 'suites': ['browser']},
        'auth': {'paths': ['app/auth.ts'], 'suites': ['browser']},
        'cli': {'paths': ['cli/**'], 'suites': ['cli']},
    },
}
HEAD = 'a' * 40


class PlanTest(unittest.TestCase):
    def test_maps_features_static_and_unknown_files(self):
        result = verify_plan.plan(['app/briefs/save.ts', 'docs/x.md'], CONFIG)
        self.assertEqual((result['features'], result['full'], result['suites']), (['briefs'], False, ['browser', 'unit']))
        docs = verify_plan.plan(['docs/a.md', 'README.md'], CONFIG)
        self.assertTrue(docs['static_only'])
        self.assertFalse(docs['needs_verifier'])
        self.assertEqual(docs['suites'], ['static', 'unit'])
        unknown = verify_plan.plan(['cli/run.py', 'lib/new.py'], CONFIG)
        self.assertTrue(unknown['full'])
        self.assertEqual(unknown['features'], ['auth', 'briefs', 'cli'])
        self.assertEqual(unknown['unmapped'], ['lib/new.py'])

    def test_gate_files_always_need_full_verification(self):
        for path in ['.jfactory/verification.json', '.github/workflows/jfactory-verified.yml']:
            self.assertTrue(verify_plan.plan([path], CONFIG)['full'], path)

    def test_glob_semantics(self):
        self.assertTrue(verify_plan.matches('a/b/c.md', ['**/*.md']))
        self.assertTrue(verify_plan.matches('c.md', ['**/*.md']))
        self.assertFalse(verify_plan.matches('app/briefsx/a.ts', ['app/briefs/**']))
        self.assertFalse(verify_plan.matches('app/x/y.ts', ['app/*.ts']))


class GateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.state = self.tmp / 'fake.json'
        bins = self.tmp / 'bin'
        bins.mkdir()
        self.env = {**os.environ, 'FAKE_STATE': str(self.state)}
        for tool in ('gh', 'git'):
            exe = bins / tool
            exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKE}" {tool} "$@"\n')
            exe.chmod(0o755)
            self.env[f'JFACTORY_{tool.upper()}'] = str(exe)
        self.write(files=['app/briefs/save.ts'])

    def write(self, files, head=HEAD, association='OWNER'):
        db = json.loads(self.state.read_text()) if self.state.exists() else {}
        pr = db.get('prs', {}).get('5', {'comments': []})
        pr.update({'headRefOid': head, 'baseRefName': 'main', 'isCrossRepository': False, 'files': files})
        db.update({'config': CONFIG, 'association': association, 'prs': {'5': pr}})
        self.state.write_text(json.dumps(db))

    def run_script(self, *args, code=0):
        proc = subprocess.run([sys.executable, str(SCRIPT), '--repo', 'o/r', *args], env=self.env,
                              capture_output=True, text=True, cwd=self.tmp)
        self.assertEqual(proc.returncode, code, proc.stdout + proc.stderr)
        return proc.stdout + proc.stderr

    def verdict(self, *extra, head=HEAD, code=0):
        return self.run_script('verdict', '--pr', '5', '--head', head, '--verdict', 'verified', '--verifier',
                               'codex/gpt-6-sol', '--implementer', 'claude/opus-5-5-1m', '--evidence',
                               'https://evidence', *extra, code=code)

    def test_status_follows_verdict_at_current_head(self):
        self.assertIn('failure: No verdict', self.run_script('check', '--pr', '5', code=1))
        self.verdict()
        self.assertIn('success: Verified', self.run_script('check', '--pr', '5'))
        self.write(files=['app/briefs/save.ts'], head='b' * 40)
        self.assertIn('No verdict for head bbbbbbb', self.run_script('check', '--pr', '5', code=1))
        self.run_script('check', '--pr', '5', '--set-status')
        status = json.loads(self.state.read_text())['statuses'][-1]
        self.assertEqual((status['state'], status['context']), ('failure', 'jfactory verified'))

    def test_verdict_refuses_stale_head_same_family_and_missing_coverage(self):
        self.assertIn('not bbbbbbb', self.verdict(head='b' * 40, code=2))
        self.assertIn('same model family', self.run_script(
            'verdict', '--pr', '5', '--head', HEAD, '--verdict', 'verified', '--verifier', 'claude/sonnet-5-1m',
            '--implementer', 'claude/opus-5-5-1m', '--evidence', 'x', code=2))
        self.write(files=['app/briefs/save.ts', 'lib/unknown.py'])
        self.assertIn('--full', self.verdict(code=2))
        self.verdict('--full')
        self.assertIn('success', self.run_script('check', '--pr', '5'))

    def test_static_only_passes_without_verifier(self):
        self.write(files=['docs/guide.md'])
        self.assertIn('success: Static-only', self.run_script('check', '--pr', '5'))

    def test_untrusted_or_partial_verdicts_do_not_pass(self):
        self.write(files=['app/briefs/save.ts'], association='NONE')
        self.verdict()
        self.assertIn('No verdict', self.run_script('check', '--pr', '5', code=1))
        self.write(files=['app/briefs/save.ts', 'app/auth.ts'])
        self.verdict('--features', 'briefs,auth', '--allow-same-family')
        db = json.loads(self.state.read_text())
        body = db['prs']['5']['comments'][-1]['body']
        record = json.loads(body.split('<!-- jfactory-verdict ')[1].split(' -->')[0])
        record['features'] = ['briefs']
        db['prs']['5']['comments'].append({'body': f'<!-- jfactory-verdict {json.dumps(record)} -->',
                                           'authorAssociation': 'OWNER'})
        self.state.write_text(json.dumps(db))
        self.assertIn('misses features: auth', self.run_script('check', '--pr', '5', code=1))


if __name__ == '__main__':
    unittest.main()
