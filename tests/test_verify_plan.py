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
        'tests': {'paths': ['tests/**'], 'suites': ['unit'], 'verify': 'ci'},
        'tooling': {'paths': ['tools/**'], 'suites': ['unit'], 'verify': 'ci'},
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
        self.assertEqual(unknown['features'], ['auth', 'briefs', 'cli', 'tests', 'tooling'])
        self.assertEqual(unknown['unmapped'], ['lib/new.py'])

    def test_risk_levels_decide_whether_a_verifier_is_needed(self):
        low = verify_plan.plan(['tests/test_a.py', 'tools/x.py', 'docs/a.md'], CONFIG)
        self.assertEqual((low['level'], low['needs_verifier']), ('ci', False))
        mixed = verify_plan.plan(['tests/test_a.py', 'app/auth.ts'], CONFIG)
        self.assertEqual((mixed['level'], mixed['needs_verifier'], verify_plan.required_features(mixed)),
                         ('independent', True, ['auth']))
        unknown = verify_plan.plan(['tests/test_a.py', 'lib/new.py'], CONFIG)
        self.assertTrue(unknown['needs_verifier'])
        self.assertIn('tests', verify_plan.required_features(unknown))
        gate = verify_plan.plan(['.jfactory/verification.json'], CONFIG)
        self.assertEqual(gate['level'], 'independent')
        self.assertEqual(verify_plan.plan(['docs/a.md'], CONFIG)['level'], 'static')

    def test_unknown_risk_level_is_refused(self):
        bad = {'features': {'x': {'paths': ['x/**'], 'verify': 'none'}}}
        (Path(tempfile.mkdtemp()) / '.jfactory').mkdir()
        root = Path(tempfile.mkdtemp())
        (root / '.jfactory').mkdir()
        (root / '.jfactory' / 'verification.json').write_text(json.dumps(bad))
        with self.assertRaises(verify_plan.Refused):
            verify_plan.load_config(root=root)

    def test_gate_files_always_need_full_verification(self):
        for path in ['.jfactory/verification.json', '.github/workflows/jfactory-verified.yml',
                     '.github/rulesets/main.json']:
            self.assertTrue(verify_plan.plan([path], CONFIG)['full'], path)

    def test_family_reads_agent_or_model(self):
        self.assertEqual(verify_plan.family('codex/gpt-6-luna'), 'openai')
        self.assertEqual(verify_plan.family('gpt-6-luna'), 'openai')
        self.assertEqual(verify_plan.family('claude/opus-5-5-1m'), 'anthropic')
        self.assertEqual(verify_plan.family('opus-5-5-1m'), 'anthropic')
        self.assertIsNone(verify_plan.family('reviewer'))
        self.assertIsNone(verify_plan.family('None/None'))

    def test_example_mapping_never_treats_agent_instructions_as_static(self):
        example = json.loads((ROOT / 'skills/jfactory/templates/verification.example.json').read_text())
        for path in ['AGENTS.md', 'CLAUDE.md', '.agents/skills/jfactory/SKILL.md',
                     '.agents/skills/verify-app/features/save-brief.md', 'app/src/lib/briefs/store.ts']:
            self.assertFalse(verify_plan.plan([path], example)['static_only'], path)
        self.assertTrue(verify_plan.plan(['docs/guide.md'], example)['static_only'])

    def test_objective_is_found_in_visible_prose(self):
        for body in ('## Objective\nSave briefs for returning users', 'Objective: https://github.com/o/r/issues/22',
                     '```\ncode\n```\n## Objective\nSave briefs for returning users',
                     '<!-- note --> Objective: save briefs for returning users',
                     '**Objective:** save briefs for returning users'):
            self.assertTrue(verify_plan.states_objective(body), body)

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

    def write(self, files, head=HEAD, association='OWNER', config=CONFIG):
        db = json.loads(self.state.read_text()) if self.state.exists() else {}
        pr = db.get('prs', {}).get('5', {'comments': []})
        pr.update({'headRefOid': head, 'baseRefName': 'main', 'isCrossRepository': False, 'files': files})
        pr.setdefault('body', '## Objective\nSave briefs.\n')
        db.update({'config': config, 'association': association, 'prs': {'5': pr}})
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
        self.assertIn('model family', self.run_script(
            'verdict', '--pr', '5', '--head', HEAD, '--verdict', 'verified', '--verifier', 'reviewer',
            '--implementer', 'claude/opus-5-5-1m', '--evidence', 'x', code=2))
        self.write(files=['app/briefs/save.ts', 'lib/unknown.py'])
        self.assertIn('--full', self.verdict(code=2))
        self.verdict('--full')
        self.assertIn('success', self.run_script('check', '--pr', '5'))

    def test_recorded_owner_decision_allows_same_family(self):
        same = ('verdict', '--pr', '5', '--head', HEAD, '--verdict', 'verified', '--verifier', 'claude/sonnet-5-1m',
                '--implementer', 'claude/opus-5-5-1m', '--evidence', 'x')
        self.assertIn('same model family', self.run_script(*same, code=2))
        self.write(files=['app/briefs/save.ts'], config={**CONFIG, 'allow_same_family': True})
        self.run_script(*same)
        self.assertIn('success: Verified', self.run_script('check', '--pr', '5'))
        self.write(files=['app/briefs/save.ts'], config=CONFIG)
        self.assertIn('same model family', self.run_script('check', '--pr', '5', code=1))

    def test_low_risk_change_passes_without_verifier_but_mixed_does_not(self):
        self.write(files=['tests/test_a.py'])
        self.assertIn('success: Low-risk change', self.run_script('check', '--pr', '5'))
        self.write(files=['tests/test_a.py', 'app/briefs/save.ts'])
        self.assertIn('No verdict', self.run_script('check', '--pr', '5', code=1))
        self.verdict('--features', 'briefs')
        self.assertIn('success: Verified', self.run_script('check', '--pr', '5'))

    def test_non_static_pr_must_state_its_objective(self):
        self.write(files=['tests/test_a.py'])
        db = json.loads(self.state.read_text())
        db['prs']['5']['body'] = 'Fixes things.'
        self.state.write_text(json.dumps(db))
        self.assertIn('does not state its objective', self.run_script('check', '--pr', '5', code=1))
        for empty in ('## Objective\n\n## Summary\nStuff', 'Objective:', 'Objective: tbd',
                      '```\n## Objective\nSave briefs for returning users\n```\n',
                      '<!--\nObjective: save briefs for returning users\n-->',
                      '```\n## Objective\nSave briefs for returning users\n',
                      '<!--\n## Objective\nSave briefs for returning users\n',
                      '````\n```\n## Objective\nSave briefs for returning users\n```\n````\n',
                      '    ## Objective\n    Save briefs for returning users\n',
                      'Intro <!-- Objective: save briefs for returning users -->'):
            db['prs']['5']['body'] = empty
            self.state.write_text(json.dumps(db))
            self.assertIn('does not state its objective', self.run_script('check', '--pr', '5', code=1), empty)
        db['prs']['5']['body'] = 'Objective: https://github.com/o/r/issues/22'
        self.state.write_text(json.dumps(db))
        self.assertIn('success: Low-risk change', self.run_script('check', '--pr', '5'))
        self.write(files=['docs/guide.md'])
        db = json.loads(self.state.read_text())
        db['prs']['5']['body'] = ''
        self.state.write_text(json.dumps(db))
        self.assertIn('success: Static-only', self.run_script('check', '--pr', '5'))

    def test_static_only_passes_without_verifier(self):
        self.write(files=['docs/guide.md'])
        self.assertIn('success: Static-only', self.run_script('check', '--pr', '5'))

    def test_untrusted_or_partial_verdicts_do_not_pass(self):
        self.write(files=['app/briefs/save.ts'], association='NONE')
        self.verdict()
        self.assertIn('No verdict', self.run_script('check', '--pr', '5', code=1))
        self.write(files=['app/briefs/save.ts', 'app/auth.ts'])
        self.verdict('--features', 'briefs,auth')
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
