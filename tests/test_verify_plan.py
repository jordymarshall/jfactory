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

    def test_plan_estimates_minutes_from_suite_timings(self):
        timed = {**CONFIG, 'suites': {'unit': {'minutes': 2}, 'browser': {'minutes': 40}}, 'pr_budget_minutes': 10}
        result = verify_plan.plan(['tools/x.py', 'cli/run.py'], timed)
        self.assertEqual((result['minutes'], result['untimed_suites'], result['budget_minutes']), (2, ['cli'], 10))
        self.assertEqual(verify_plan.plan(['app/briefs/save.ts'], timed)['minutes'], 42)
        self.assertIn('Estimated CI time: 2 min plus untimed cli (per-PR budget 10 min)', verify_plan.render_plan(result))

    def test_gate_change_needs_a_full_verdict_but_not_every_journey(self):
        gate = verify_plan.plan(['.jfactory/setup.md'], CONFIG)
        self.assertEqual((gate['full'], gate['features'], gate['suites'], gate['level']),
                         (True, [], ['browser', 'unit'], 'independent'))
        narrow = {**CONFIG, 'full_suites': ['unit']}
        self.assertEqual(verify_plan.plan(['.jfactory/verification.json', 'cli/run.py'], narrow)['suites'], ['cli', 'unit'])
        # Unmapped code still pulls in every feature, which is why audit and ci refuse unmapped files.
        self.assertIn('browser', verify_plan.plan(['lib/new.py'], narrow)['suites'])

    def test_audit_finds_map_gaps_and_cost_problems(self):
        files = ['app/briefs/a.ts', 'app/auth.ts', 'cli/run.py', 'tests/test_a.py', 'tools/x.py', 'docs/a.md']
        config = {**CONFIG, 'full_suites': ['unit'], 'pr_budget_minutes': 10,
                  'suites': {s: {'run': f'echo {s}', 'minutes': 1} for s in ['unit', 'static', 'browser', 'cli']}}
        levels = lambda items: [level for level, _ in items]
        self.assertNotIn('FAIL', levels(verify_plan.audit(files, config)))
        text = lambda items: '\n'.join(f'{level}: {t}' for level, t in items)
        self.assertIn('FAIL: 1 tracked file(s) match no feature', text(verify_plan.audit(files + ['lib/new.py'], config)))
        self.assertIn('Feature(s) cli match no tracked file', text(verify_plan.audit(files[:2] + files[3:], config)))
        undefined = {**config, 'suites': {'unit': {'run': 'x', 'minutes': 1}}}
        self.assertIn('FAIL: Suite(s) browser, cli, static are used but not defined', text(verify_plan.audit(files, undefined)))
        slow = {**config, 'suites': {**config['suites'], 'browser': {'run': 'x', 'minutes': 45}}}
        self.assertIn('WARN: These changes exceed the 10 min per-PR budget: app/briefs/a.ts -> briefs (46 min)',
                      text(verify_plan.audit(files, slow)))
        self.assertIn('FAIL: Suites that run on every PR take 47 min',
                      text(verify_plan.audit(files, {**slow, 'always_suites': ['unit', 'browser']})))
        self.assertIn('FAIL: A gate change runs always_suites and full_suites for 46 min',
                      text(verify_plan.audit(files, {**slow, 'full_suites': ['unit', 'browser']})))
        broken = {**config, 'targets': {'local': {'start': 'npm start'}}}
        self.assertIn('FAIL: Target local needs "ready"', text(verify_plan.audit(files, broken)))
        many = [f'app/briefs/{i}.ts' for i in range(30)] + files
        self.assertIn('WARN: Feature briefs covers 31 of', text(verify_plan.audit(many, config)))

    def test_recorded_coverage_adds_the_journeys_that_execute_a_change(self):
        config = {**CONFIG, 'suites': {s: {'minutes': m} for s, m in
                                       [('unit', 1), ('browser', 20), ('cli', 2), ('static', 1)]}}
        impact = {'browser': {'tools/x.py', 'app/briefs/save.ts'}, 'unknown-suite': {'tools/x.py'}}
        result = verify_plan.plan(['tools/x.py'], config, impact)
        self.assertEqual((result['suites'], result['impact']), (['browser', 'unit'], {'browser': ['tools/x.py']}))
        self.assertIn('`browser` executes `tools/x.py`', verify_plan.render_plan(result))
        # Coverage only adds: a mapped suite stays even when coverage never saw the file.
        self.assertEqual(verify_plan.plan(['cli/run.py'], config, {'browser': set()})['suites'], ['cli', 'unit'])

    def test_coverage_formats_are_read_as_repository_paths(self):
        root = Path(tempfile.mkdtemp())
        write = lambda name, data: (root / name).write_text(data if isinstance(data, str) else json.dumps(data))
        write('istanbul.json', {str(root / 'app/a.ts'): {'path': str(root / 'app/a.ts'), 's': {'0': 3}, 'f': {'0': 1}},
                                str(root / 'app/b.ts'): {'path': str(root / 'app/b.ts'), 's': {'0': 1}, 'f': {'0': 0}}})
        ran = lambda count: [{'functionName': '', 'ranges': [{'count': 1}]}, {'functionName': 'load', 'ranges': [{'count': count}]}]
        write('v8.json', {'result': [{'url': f'file://{root}/lib/db.js', 'functions': ran(2)},
                                     {'url': f'file://{root}/lib/loaded-only.js', 'functions': ran(0)},
                                     {'url': 'file:///elsewhere/x.js', 'functions': ran(1)}]})
        write('coverage.json', {'files': {'svc/api.py': {'executed_lines': [1]}, 'svc/idle.py': {'executed_lines': []}}})
        write('list.txt', 'app/c.ts\n\n')
        read = lambda name: verify_plan.coverage_files(root / name, root)
        self.assertEqual((read('istanbul.json'), read('v8.json'), read('coverage.json'), read('list.txt')),
                         ({'app/a.ts'}, {'lib/db.js'}, {'svc/api.py'}, {'app/c.ts'}))
        (root / 'impact').mkdir()
        (root / 'impact' / '1.json').write_text(json.dumps({'suites': {'a': ['x'], 'b': ['y']}}))
        (root / 'impact' / '2.json').write_text(json.dumps({'suites': {'a': ['z']}}))
        self.assertEqual(verify_plan.load_impact(root / 'impact'), {'a': {'x', 'z'}, 'b': {'y'}})
        self.assertEqual(verify_plan.load_impact(root / 'missing'), {})

    def test_shards_balance_suites_by_minutes(self):
        config = {'suites': {'a': {'minutes': 20}, 'b': {'minutes': 12}, 'c': {'minutes': 9}, 'd': {'minutes': 3}},
                  'shards': 2}
        self.assertEqual(verify_plan.binpack(['a', 'b', 'c', 'd'], config, 2), [['a', 'd'], ['b', 'c']])
        result = verify_plan.plan(['x'], {**config, 'features': {'f': {'paths': ['x'], 'suites': ['a', 'b', 'c', 'd']}}})
        self.assertEqual((result['minutes'], result['wall_minutes']), (44, 23))

    def test_journeys_never_run_on_every_pr(self):
        config = {'always_suites': ['unit', 'e2e'], 'features': {'f': {'paths': ['x'], 'suites': ['unit']}},
                  'suites': {'unit': {'run': 'x', 'minutes': 1}, 'e2e': {'run': 'x', 'minutes': 45, 'target': 'local'}},
                  'targets': {'local': {'start': 'x', 'ready': 'http://x', 'auth': 'none'}}}
        self.assertIn(('FAIL', 'always_suites include journey suite(s) e2e, so every PR would drive the app; attach '
                               'them to the features they check'), verify_plan.audit(['x'], config))

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
                     '\n\n## Objective\n\nSave briefs for returning users\n\n## Summary\nx',
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
        self.assertIn('must start with its objective', self.run_script('check', '--pr', '5', code=1))
        for empty in ('## Objective\n\n## Summary\nStuff', 'Objective:', 'Objective: tbd',
                      '```\n## Objective\nSave briefs for returning users\n```\n',
                      '<!--\nObjective: save briefs for returning users\n-->',
                      '```\n## Objective\nSave briefs for returning users\n',
                      '<!--\n## Objective\nSave briefs for returning users\n',
                      '````\n```\n## Objective\nSave briefs for returning users\n```\n````\n',
                      '    ## Objective\n    Save briefs for returning users\n',
                      'Intro <!-- Objective: save briefs for returning users -->',
                      '- item\n  ```md\n  ## Objective\n  Save briefs for returning users\n  ```\n',
                      '<details><summary>More</summary>\n\n## Objective\nSave briefs for returning users\n</details>',
                      '## Summary\nStuff\n\n## Objective\nSave briefs for returning users'):
            db['prs']['5']['body'] = empty
            self.state.write_text(json.dumps(db))
            self.assertIn('must start with its objective', self.run_script('check', '--pr', '5', code=1), empty)
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


HTTP = f'"{sys.executable}" -m http.server $PORT --bind 127.0.0.1'


class RunTest(unittest.TestCase):
    """`ci` and `smoke` against a real git repository and a real local server."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        git = lambda *a: subprocess.run(['git', '-C', str(self.root), '-c', 'user.name=t', '-c', 'user.email=t@t', *a],
                                        check=True, capture_output=True)
        self.git = git
        git('init', '-q', '-b', 'main')
        for path in ['app/briefs/a.py', 'cli/run.py', 'README.md']:
            (self.root / '.gitignore').write_text('ran-*\nimpact/\n')
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            (self.root / path).write_text('x\n')
        (self.root / '.jfactory').mkdir()
        self.config = {
            'static': ['README.md', '.gitignore'], 'always_suites': ['unit'], 'full_suites': ['unit'], 'pr_budget_minutes': 10,
            'suites': {'unit': {'run': 'touch ran-unit', 'minutes': 1},
                       'browser-briefs': {'run': 'curl -sf "$BASE_URL/" -o /dev/null && touch ran-browser',
                                          'minutes': 2, 'target': 'local'},
                       'cli': {'run': 'touch ran-cli', 'minutes': 1}},
            'targets': {'local': {'start': HTTP, 'ready': 'http://127.0.0.1:$PORT/', 'auth': 'none',
                                  'doctor': 'true', 'probe': 'curl -sf "$BASE_URL/README.md" -o /dev/null'}},
            'features': {'briefs': {'paths': ['app/briefs/**'], 'suites': ['unit', 'browser-briefs']},
                         'cli': {'paths': ['cli/**'], 'suites': ['unit', 'cli']}}}
        self.write_config()
        git('add', '-A')
        git('commit', '-qm', 'base')
        git('checkout', '-qb', 'task')

    def write_config(self, **changes):
        (self.root / '.jfactory' / 'verification.json').write_text(json.dumps({**self.config, **changes}))

    def run_script(self, *args, code=0):
        proc = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=self.root, capture_output=True, text=True,
                              timeout=120)
        self.assertEqual(proc.returncode, code, proc.stdout + proc.stderr)
        return proc.stdout + proc.stderr

    def change(self, path):
        (self.root / path).parent.mkdir(parents=True, exist_ok=True)
        (self.root / path).write_text('changed\n')
        self.git('add', '-A')
        self.git('commit', '-qm', 'change')

    def ran(self):
        return sorted(p.name for p in self.root.glob('ran-*'))

    def test_ci_runs_only_the_changed_features_suites(self):
        self.change('cli/run.py')
        out = self.run_script('ci', '--base', 'main')
        self.assertEqual(self.ran(), ['ran-cli', 'ran-unit'])
        self.assertIn('cli: passed', out)

    def test_ci_starts_the_target_for_a_journey_suite(self):
        self.change('app/briefs/a.py')
        self.run_script('ci', '--base', 'main')
        self.assertEqual(self.ran(), ['ran-browser', 'ran-unit'])

    def test_ci_refuses_unmapped_files_before_running_anything(self):
        self.change('lib/new.py')
        out = self.run_script('ci', '--base', 'main', code=1)
        self.assertIn('lib/new.py', out)
        self.assertEqual(self.ran(), [])

    def test_ci_fails_when_a_suite_fails_or_the_target_never_starts(self):
        self.write_config(suites={**self.config['suites'], 'cli': {'run': 'exit 3', 'minutes': 1}})
        self.change('cli/run.py')
        self.assertIn('cli: failed (3)', self.run_script('ci', '--base', 'main', code=1))
        self.write_config(targets={'local': {**self.config['targets']['local'], 'start': 'exit 1'}})
        self.change('app/briefs/a.py')
        self.assertIn('start command exited with 1', self.run_script('ci', '--base', 'main', code=1))

    def test_ci_all_runs_every_suite(self):
        self.run_script('ci', '--all')
        self.assertEqual(self.ran(), ['ran-browser', 'ran-cli', 'ran-unit'])

    def test_ci_shard_runs_its_share_of_the_plan(self):
        self.run_script('ci', '--all', '--shard', '1/2')
        first = self.ran()
        for marker in self.root.glob('ran-*'):
            marker.unlink()
        self.run_script('ci', '--all', '--shard', '2/2')
        self.assertEqual(sorted(first + self.ran()), ['ran-browser', 'ran-cli', 'ran-unit'])
        self.assertTrue(first and self.ran())

    def test_recorded_coverage_selects_journeys_for_shared_code(self):
        # The journey's app is a Node server; NODE_V8_COVERAGE records what it executed.
        (self.root / 'lib').mkdir()
        (self.root / 'lib' / 'db.js').write_text('exports.load = () => "Briefs";\n')
        (self.root / 'server.js').write_text(
            'const http = require("http"); const db = require("./lib/db");\n'
            'process.on("SIGTERM", () => process.exit(0));\n'
            'http.createServer((q, s) => s.end(db.load())).listen(+process.argv[2], "127.0.0.1");\n')
        # `; true` keeps the shell alive as Node's parent, as dash does on Ubuntu runners, so stopping must wait
        # for the whole process group before reading coverage.
        local = {**self.config['targets']['local'], 'start': 'node server.js $PORT; true'}
        features = {**self.config['features'], 'shared': {'paths': ['lib/**', 'server.js'], 'suites': ['unit']}}
        self.write_config(targets={'local': local}, features=features)
        self.git('add', '-A')
        self.git('commit', '-qm', 'node app')
        self.run_script('ci', '--all', '--impact-out', 'impact/nightly.json')
        recorded = json.loads((self.root / 'impact' / 'nightly.json').read_text())['suites']
        self.assertEqual(recorded, {'browser-briefs': ['lib/db.js', 'server.js']})
        for marker in self.root.glob('ran-*'):
            marker.unlink()
        (self.root / 'lib' / 'db.js').write_text('exports.load = () => "Saved briefs";\n')
        self.git('commit', '-qam', 'shared change')
        out = self.run_script('ci', '--base', 'HEAD~1', '--impact', 'impact')
        self.assertIn('`browser-briefs` executes `lib/db.js`', out)
        self.assertEqual(self.ran(), ['ran-browser', 'ran-unit'])
        for marker in self.root.glob('ran-*'):
            marker.unlink()
        # Without coverage, the same change runs only the shared feature's own suites.
        self.run_script('ci', '--base', 'HEAD~1', '--impact', 'nowhere')
        self.assertEqual(self.ran(), ['ran-unit'])

    def test_smoke_records_a_receipt_and_reports_the_failed_step(self):
        out = self.run_script('smoke', '--target', 'local', '--fresh', '--record', '.jfactory/smoke.json')
        self.assertIn('Target local is ready', out)
        receipt = json.loads((self.root / '.jfactory' / 'smoke.json').read_text())['local']
        self.assertEqual((receipt['ok'], receipt['fresh'], [s['step'] for s in receipt['steps']]),
                         (True, True, ['doctor', 'ready', 'probe']))
        self.write_config(targets={'local': {**self.config['targets']['local'], 'doctor': 'echo missing DATABASE_URL; exit 2'}})
        out = self.run_script('smoke', '--target', 'local', '--record', '.jfactory/smoke.json', code=1)
        self.assertIn('FAIL: doctor', out)
        self.assertFalse(json.loads((self.root / '.jfactory' / 'smoke.json').read_text())['local']['ok'])
        self.write_config(targets={'local': {**self.config['targets']['local'], 'start': 'sleep 30'}})
        out = self.run_script('smoke', '--target', 'local', '--timeout', '2', code=1)
        self.assertIn('did not answer within 2s', out)
