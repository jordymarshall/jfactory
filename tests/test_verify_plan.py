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
        'lint': {'paths': ['lint/**'], 'suites': ['unit'], 'verify': 'ci'},
        'tooling': {'paths': ['tools/**'], 'suites': ['unit'], 'verify': 'ci'},
    },
}
HEAD = 'a' * 40
RULE = ('skills/jfactory/references/verification.md#independent-verdict: prescribes GPT Sol 6.1 at high effort, but '
        'the owner moved the verify tier to low-effort fast mode; point to the verify tier in models.md instead')


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
        self.assertEqual(unknown['features'], ['auth', 'briefs', 'cli', 'lint', 'tooling'])
        self.assertEqual(unknown['unmapped'], ['lib/new.py'])

    def test_risk_levels_decide_whether_a_verifier_is_needed(self):
        low = verify_plan.plan(['lint/rules.py', 'tools/x.py', 'docs/a.md'], CONFIG)
        self.assertEqual((low['level'], low['needs_verifier']), ('ci', False))
        mixed = verify_plan.plan(['lint/rules.py', 'app/auth.ts'], CONFIG)
        self.assertEqual((mixed['level'], mixed['needs_verifier'], verify_plan.required_features(mixed)),
                         ('independent', True, ['auth']))
        unknown = verify_plan.plan(['lint/rules.py', 'lib/new.py'], CONFIG)
        self.assertTrue(unknown['needs_verifier'])
        self.assertIn('lint', verify_plan.required_features(unknown))
        gate = verify_plan.plan(['.jfactory/verification.json'], CONFIG)
        self.assertEqual(gate['level'], 'independent')
        self.assertEqual(verify_plan.plan(['docs/a.md'], CONFIG)['level'], 'static')

    def test_tests_instructions_and_screens_always_need_the_verifier(self):
        # A `ci` feature stays CI-only for its ordinary code: the negative control.
        self.assertEqual(verify_plan.plan(['tools/x.py'], CONFIG)['level'], 'ci')
        for path, why in (('tools/x.test.ts', 'tests'), ('tools/e2e/flow.ts', 'tests'),
                          ('tools/AGENTS.md', 'agent instructions'), ('tools/skill/SKILL.md', 'agent instructions')):
            result = verify_plan.plan([path], CONFIG)
            self.assertEqual((result['level'], result['independent_features'], result['overridden']),
                             ('independent', ['tooling'], {'tooling': why}), path)
        # Nested agent-rule folders and other test runners' files count too (verifier findings on #30).
        nested = {'static': ['**/*.md'], 'features': {'internal': {
            'paths': ['packages/**', 'src/**', 'cypress/**', 'cypress.config.ts', 'spec/**', 'pkg/**', '.*'],
            'verify': 'ci'}}}
        for path in ('packages/web/.claude/rules/security.md', 'packages/web/.cursor/rules/style.mdc',
                     'packages/web/.agents/skills/review/references/policy.md', 'packages/web/.cursorrules',
                     'cypress.config.ts', 'cypress/support/component.ts', 'src/components/Nav.cy.tsx',
                     'src/models/user_spec.rb', 'spec/support/auth.rb', '.mocharc.yml', '.clinerules/general.md',
                     'packages/web/.clinerules/security.md', 'spec/fixtures/users.yml', 'spec/factories.rb',
                     'packages/core/spec/fixtures/users.yml', 'src/runtime/spec/format.ts', 'pkg/testdata/golden.json',
                     'src/test/java/AppTest.java', '.mocharc.mjs', 'packages/core/.mocharc.mjs'):
            self.assertEqual(verify_plan.plan([path], nested)['level'], 'independent', path)
        for path in ('src/lib/format.ts', 'src/app/api/health/route.ts', 'packages/web/src/specification.ts',
                     'src/generated/api_spec.json'):
            self.assertEqual(verify_plan.plan([path], nested)['level'], 'ci', path)
        # Prose that only names a spec stays static.
        for path in ('docs/spec/architecture.md', 'docs/api_spec.md', 'docs/.mocharc.md'):
            self.assertTrue(verify_plan.plan([path], {**nested, 'static': ['docs/**']})['static_only'], path)
        loose = {**nested, 'features': {}}
        self.assertEqual(verify_plan.plan(['packages/web/.claude/rules/security.md'], loose)['unmapped'],
                         ['packages/web/.claude/rules/security.md'])
        self.assertTrue(verify_plan.plan(['packages/web/docs/guide.md'], loose)['static_only'])
        self.assertEqual(verify_plan.plan(['.clinerules/general.md'], loose)['unmapped'], ['.clinerules/general.md'])
        # Test code inside a static folder is never static; prose there may be.
        docs = {'static': ['docs/**'], 'features': {}}
        self.assertEqual(verify_plan.plan(['docs/tests/flow.test.ts'], docs)['unmapped'], ['docs/tests/flow.test.ts'])
        self.assertTrue(verify_plan.plan(['docs/tests/README.md'], docs)['static_only'])
        self.assertTrue(verify_plan.plan(['docs/tests/README.txt'], docs)['static_only'])
        for path in ('docs/tests/flow.test.txt', 'docs/flow.test.txt'):
            self.assertEqual(verify_plan.plan([path], docs)['unmapped'], [path])
        self.assertIn('Marked `ci` but reviewed anyway: `tooling` (tests)',
                      verify_plan.render_plan(verify_plan.plan(['tools/x.test.ts'], CONFIG)))
        # Instructions are never static, even when a static pattern covers all Markdown.
        root = verify_plan.plan(['AGENTS.md'], CONFIG)
        self.assertEqual((root['unmapped'], root['full']), (['AGENTS.md'], True))
        self.assertTrue(verify_plan.plan(['docs/a.md'], CONFIG)['static_only'])
        screens = {**CONFIG, 'suites': {'journey': {'target': 'app'}, 'unit': {}},
                   'features': {**CONFIG['features'],
                                'shell': {'paths': ['app/shell/**'], 'suites': ['journey'], 'verify': 'ci'},
                                'copy': {'paths': ['app/copy/**'], 'suites': ['unit'], 'verify': 'ci', 'screens': True}}}
        for path, fid in (('app/shell/nav.tsx', 'shell'), ('app/copy/en.json', 'copy')):
            result = verify_plan.plan([path], screens)
            self.assertEqual((result['level'], result['overridden']), ('independent', {fid: 'screens users see'}))
        self.assertEqual(verify_plan.plan(['tools/x.py'], screens)['level'], 'ci')
        text = '\n'.join(f'{level}: {t}' for level, t in verify_plan.audit(
            ['app/shell/nav.tsx', 'app/copy/en.json', 'tools/x.py', 'tools/x.test.ts', 'AGENTS.md'], screens))
        self.assertIn('WARN: Feature shell is marked ci but has screens users see', text)
        self.assertIn('WARN: Feature copy is marked ci but has screens users see', text)
        self.assertIn('WARN: Feature tooling is marked ci, but changes to its tests always get', text)
        self.assertIn('FAIL: Static patterns cover tests, agent instructions or standards documents, which always need review: AGENTS.md', text)

    def test_owner_chooses_when_the_whole_suite_runs(self):
        mode = verify_plan.full_suite_mode
        # Unset keeps the earlier behaviour: nightly, plus the label and manual runs.
        self.assertEqual([mode({}, e) for e in ('pull_request', 'schedule', 'push', 'workflow_dispatch')],
                         ['planned', 'full', 'skip', 'full'])
        request = {'full_suite': 'on-request'}
        self.assertEqual([mode(request, e) for e in ('pull_request', 'schedule', 'push', 'workflow_dispatch')],
                         ['planned', 'skip', 'skip', 'full'])
        self.assertEqual(mode(request, 'pull_request', ['bug', 'full-suite']), 'full')
        self.assertEqual(mode({**request, 'full_suite_label': 'release'}, 'pull_request', ['full-suite']), 'planned')
        self.assertEqual(mode({'full_suite': 'merge'}, 'push'), 'full')
        self.assertEqual(mode({'full_suite': 'merge'}, 'schedule'), 'skip')
        self.assertEqual(mode({'full_suite': 'every-pr'}, 'pull_request'), 'full')
        journeys = {**CONFIG, 'suites': {'unit': {'run': 'true', 'minutes': 2}, 'browser': {'run': 'true', 'minutes': 40,
                                                                                        'target': 'app'},
                                         'static': {'run': 'true', 'minutes': 1}, 'cli': {'run': 'true', 'minutes': 1}},
                    'targets': {'app': {'url': 'http://x', 'ready': 'http://x', 'auth': 'none'}}}
        files = ['app/briefs/a.ts', 'app/auth.ts', 'cli/run.py', 'lint/rules.py', 'tools/x.py', 'docs/a.md']
        text = lambda config: '\n'.join(f'{level}: {t}' for level, t in verify_plan.audit(files, config))
        self.assertIn('WARN: The owner has not chosen when the whole suite (about 44 min) runs', text(journeys))
        self.assertIn('PASS: The whole suite (about 44 min) runs only when asked for',
                      text({**journeys, 'full_suite': 'on-request'}))
        self.assertIn('FAIL: "full_suite" is "weekly"', text({**journeys, 'full_suite': 'weekly'}))
        self.assertIn('jfactory recommends "on-request": the whole suite takes about 44 min, and journeys share one '
                      'account on app', text(journeys))
        self.assertIn('jfactory would recommend "on-request"', text({**journeys, 'full_suite': 'nightly'}))
        # A map without journeys has nothing to schedule.
        self.assertNotIn('whole suite', text(CONFIG))

    def test_recommendation_follows_the_suite_cost_and_test_data(self):
        seeded = {'app': {'url': 'http://x', 'ready': 'http://x', 'auth': 'none', 'seed': 'make seed', 'cleanup': 'make clean'}}
        def advise(minutes, shards=1, targets=seeded):
            suites = {'unit': {'run': 'true', 'minutes': 1}, 'e2e': {'run': 'true', 'minutes': minutes - 1, 'target': 'app'}}
            return verify_plan.recommend_full_suite({'suites': suites, 'targets': targets, 'shards': shards})
        self.assertEqual(advise(4)[0], 'every-pr')
        self.assertEqual(advise(12)[0], 'nightly')
        self.assertEqual(advise(40)[0], 'on-request')
        # Parallel jobs shorten the wait, so a longer suite still fits a nightly run.
        e2e = {f'e2e{i}': {'run': 'true', 'minutes': 10, 'target': 'app'} for i in range(4)}
        self.assertEqual(verify_plan.recommend_full_suite({'suites': e2e, 'targets': seeded, 'shards': 4}),
                         ('nightly', 'the whole suite takes about 40 min (10 min across 4 jobs), affordable once a day '
                                     'with no one waiting on it'))
        # An unmeasured suite makes the cost unknown, so the advice stays conservative instead of "cheap".
        untimed = {'unit': {'run': 'true', 'minutes': 1}, 'e2e': {'run': 'true', 'target': 'app'}}
        advice = verify_plan.recommend_full_suite({'suites': untimed, 'targets': seeded})
        self.assertEqual(advice[0], 'on-request')
        self.assertIn('e2e have no measured minutes', advice[1])
        # A shared account makes any long whole-suite run block the others, whatever its length.
        shared = {'app': {'url': 'http://x', 'ready': 'http://x', 'auth': 'none'}}
        self.assertEqual(advise(12, targets=shared)[0], 'on-request')

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
        files = ['app/briefs/a.ts', 'app/auth.ts', 'cli/run.py', 'lint/rules.py', 'tools/x.py', 'docs/a.md']
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
        for tool in ('gh', 'git', 'conductor'):
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

    def test_screen_changes_need_reviewed_screenshots(self):
        screens = {**CONFIG, 'suites': {'browser': {'run': 'true', 'target': 'app'}},
                   'targets': {'app': {'url': 'http://x', 'ready': 'http://x', 'auth': 'none'}}}
        self.write(files=['app/briefs/save.ts'], config=screens)
        self.assertIn('touches screens users see', self.verdict(code=2))
        # A verdict posted without them (for example by hand) still does not count.
        db = json.loads(self.state.read_text())
        db['prs']['5']['comments'].append({'authorAssociation': 'OWNER', 'body': '<!-- jfactory-verdict ' + json.dumps(
            {'head': HEAD, 'verdict': 'verified', 'features': ['auth', 'briefs'], 'full': False,
             'verifier': 'codex/gpt-6-sol', 'implementer': 'claude/opus-5-5-1m', 'evidence': ['x']}) + ' -->'})
        self.state.write_text(json.dumps(db))
        self.assertIn('no step-by-step walkthrough', self.run_script('check', '--pr', '5', code=1))
        db = json.loads(self.state.read_text())
        body = db['prs']['5']['comments'][-1]['body'].replace('"evidence": ["x"]', '"evidence": ["x"], "walkthrough": ["w"]')
        db['prs']['5']['comments'][-1]['body'] = body
        self.state.write_text(json.dumps(db))
        self.assertIn('no screenshots of the changed screens (briefs)', self.run_script('check', '--pr', '5', code=1))
        self.assertIn('step by step', self.verdict('--screenshots', 'https://shots/briefs-desktop.png', code=2))
        self.verdict('--screenshots', 'https://shots/briefs-desktop.png', '--screenshots', 'https://shots/briefs-mobile.png',
                     '--walkthrough', 'https://trail/briefs-desktop.html', '--walkthrough', 'https://trail/briefs-mobile.html')
        self.assertIn('success: Verified', self.run_script('check', '--pr', '5'))
        posted = json.loads(self.state.read_text())['prs']['5']['comments'][-1]['body']
        self.assertIn('Screenshots reviewed:', posted)
        self.assertIn('Step-by-step walkthrough:', posted)
        # Turning screenshots off does not turn the walkthrough off.
        self.write(files=['app/briefs/save.ts'], head='9' * 40, config={**screens, 'require_screenshots': False})
        self.assertIn('step by step', self.verdict(head='9' * 40, code=2))
        self.verdict('--walkthrough', 'https://trail/b.html', head='9' * 40)
        self.assertIn('success: Verified', self.run_script('check', '--pr', '5'))
        # Changes without screens, and repositories that opt out, need none. Neither do test-only or prose-only
        # changes inside a screen feature: they still get the independent review, just not screenshots.
        self.write(files=['cli/run.py'], head='c' * 40, config=screens)
        self.verdict(head='c' * 40)
        for i, files in enumerate((['app/briefs/save.test.ts'], ['app/briefs/README.md'], ['app/briefs/e2e/flow.ts'])):
            head = str(i) * 40
            self.write(files=files, head=head, config=screens)
            self.assertEqual(verify_plan.plan(files, screens)['screen_features'], [], files)
            self.verdict(head=head)
        # Rendered MDX is a screen, and so is a new unmapped screen, even alongside its mapping update.
        self.assertEqual(verify_plan.plan(['app/briefs/page.mdx'], screens)['screen_features'], ['briefs'])
        new_screen = ['app/new-screen/page.tsx', '.jfactory/verification.json']
        self.assertEqual(verify_plan.plan(new_screen, screens)['screen_features'], ['auth', 'briefs'])
        self.write(files=new_screen, head='e' * 40, config=screens)
        self.assertIn('touches screens users see', self.verdict('--full', head='e' * 40, code=2))
        self.verdict('--full', '--screenshots', 'https://shots/new.png', '--walkthrough', 'https://trail/new.html', head='e' * 40)
        self.assertIn('success: Verified', self.run_script('check', '--pr', '5'))
        # A later head re-checked with --since still needs them.
        self.write(files=new_screen, head='f' * 40, config=screens)
        self.assertIn('touches screens users see', self.verdict('--full', '--since', 'e' * 40, head='f' * 40, code=2))
        # Unmapped docs or tests stay exempt.
        self.assertEqual(verify_plan.plan(['notes/todo.md', 'tools/x.test.ts'], screens)['screen_features'], [])
        # A mixed change still needs them.
        self.assertEqual(verify_plan.plan(['app/briefs/save.test.ts', 'app/briefs/save.ts'], screens)['screen_features'],
                         ['briefs'])
        self.write(files=['app/briefs/save.ts'], head='d' * 40, config={**screens, 'require_screenshots': False, 'require_walkthrough': False})
        self.verdict(head='d' * 40)
        self.assertIn('success: Verified', self.run_script('check', '--pr', '5'))

    def test_verdicts_name_the_standards_and_journeys_they_checked(self):
        standards = ('| Dimension | Source of truth | How changes are checked |\n| --- | --- | --- |\n'
                     '| Brand, voice and copy | `docs/brand.md` | Rubric |\n')
        config = {**CONFIG, 'features': {**CONFIG['features'], 'briefs': {**CONFIG['features']['briefs'],
                                                                           'journey': 'docs/journeys/briefs.md'}}}
        self.write(files=['app/briefs/save.ts'], config=config)
        db = json.loads(self.state.read_text())
        db['standards'] = standards
        self.state.write_text(json.dumps(db))
        self.assertIn('name each with --standards', self.verdict(code=2))
        self.assertIn('is not a source', self.verdict('--standards', 'docs/other.md', code=2))
        self.verdict('--standards', 'docs/brand.md#voice', '--standards', 'docs/journeys/briefs.md')
        self.assertIn('success: Verified', self.run_script('check', '--pr', '5'))
        self.assertIn('Checked against standards:', json.loads(self.state.read_text())['prs']['5']['comments'][-1]['body'])
        # A verdict posted without them does not count.
        db = json.loads(self.state.read_text())
        db['prs']['5']['comments'].append({'authorAssociation': 'OWNER', 'body': '<!-- jfactory-verdict ' + json.dumps(
            {'head': HEAD, 'verdict': 'verified', 'features': ['auth', 'briefs'], 'full': False,
             'verifier': 'codex/gpt-6-sol', 'implementer': 'claude/opus-5-5-1m', 'evidence': ['x']}) + ' -->'})
        self.state.write_text(json.dumps(db))
        self.assertIn('does not name the standards', self.run_script('check', '--pr', '5', code=1))
        # With outcomes/ documents, the PR itself must name the ones it serves.
        config['features']['briefs']['journey'] = 'outcomes/save-a-brief.md'
        self.write(files=['app/briefs/save.ts'], head='e' * 40, config=config)
        self.assertIn('needs a "Why it\'s right" section', self.run_script('check', '--pr', '5', code=1))
        db = json.loads(self.state.read_text())
        db['prs']['5']['body'] = "## Objective\nSave briefs.\n\n## Why it's right\nIt serves the outcomes.\n"
        self.state.write_text(json.dumps(db))
        self.assertIn('must name the outcomes/<job>.md document(s)', self.run_script('check', '--pr', '5', code=1))
        db = json.loads(self.state.read_text())
        db['prs']['5']['body'] = "## Objective\nSave briefs.\n\n## Why it's right\nServes `outcomes/save-a-brief.md`.\n"
        self.state.write_text(json.dumps(db))
        self.assertIn('No verdict', self.run_script('check', '--pr', '5', code=1))
        # Docs-only changes need none.
        self.write(files=['docs/a.md'], head='c' * 40, config=config)
        self.assertIn('success: Static-only', self.run_script('check', '--pr', '5'))

    def test_citations_must_name_real_sources_and_a_failed_verdict_vetoes(self):
        standards = ('| Dimension | Source of truth | How changes are checked |\n| --- | --- | --- |\n'
                     '| Brand, voice and copy | `docs/brand.md` | Rubric |\n')
        self.write(files=['app/briefs/save.ts'], config=CONFIG)
        db = json.loads(self.state.read_text())
        db['standards'] = standards
        self.state.write_text(json.dumps(db))
        for cited in ([''], ['docs/invented.md'], 'docs/brand.md', [7]):
            db = json.loads(self.state.read_text())
            db['prs']['5']['comments'] = [{'authorAssociation': 'OWNER', 'body': '<!-- jfactory-verdict ' + json.dumps(
                {'head': HEAD, 'verdict': 'verified', 'features': ['auth', 'briefs'], 'full': False, 'standards': cited,
                 'verifier': 'codex/gpt-6-sol', 'implementer': 'claude/opus-5-5-1m', 'evidence': ['x']}) + ' -->'}]
            self.state.write_text(json.dumps(db))
            self.assertIn('does not name the standards', self.run_script('check', '--pr', '5', code=1), cited)
        self.assertIn('is not a source', self.verdict('--standards', '../docs/brand.md', code=2))
        self.verdict('--standards', './docs/brand.md#voice')
        self.assertIn('success: Verified', self.run_script('check', '--pr', '5'))
        # Done means right: a failed verdict vetoes even a change that needed none.
        self.write(files=['lint/rules.py'], head='c' * 40, config=CONFIG)
        self.assertIn('success: Low-risk', self.run_script('check', '--pr', '5'))
        self.run_script('verdict', '--pr', '5', '--head', 'c' * 40, '--verdict', 'failed', '--cause', 'change', '--verifier', 'codex/gpt-6-sol',
                        '--implementer', 'claude/opus-5-5-1m', '--evidence', 'https://evidence')
        self.assertIn('Latest verdict at ccccccc is failed', self.run_script('check', '--pr', '5', code=1))

    def test_standards_and_journey_documents_are_always_reviewed(self):
        config = {**CONFIG, '_standards': ['docs/brand.md', 'docs/journeys/briefs.md'],
                  'features': {**CONFIG['features'], 'docs': {'paths': ['docs/journeys/**'], 'verify': 'ci'}}}
        # The brand guide is only covered by the Markdown static pattern, so it is unmapped: full verification.
        brand = verify_plan.plan(['docs/brand.md'], config)
        self.assertEqual((brand['unmapped'], brand['full'], brand['static_only']), (['docs/brand.md'], True, False))
        journey = verify_plan.plan(['docs/journeys/briefs.md'], config)
        self.assertEqual((journey['level'], journey['overridden']), ('independent', {'docs': 'standards'}))
        self.assertTrue(verify_plan.plan(['docs/guide.md'], config)['static_only'])

    def test_proof_headers_must_precede_a_table_separator(self):
        methods = ('| Method | How it applies |\n| --- | --- |\n'
                   '| Observe | Capture proof from the actual artifact |\n'
                   '| Clean | Retain evidence |\n')
        self.assertEqual(verify_plan.journey_proofs(methods), [])
        goals = "| Goal | How it's proven |\n| --- | --- |\n| Preserve edits | Reload and read saved text |\n"
        self.assertEqual(verify_plan.journey_proofs(methods + '\n' + goals),
                         [('Preserve edits', 'Reload and read saved text')])
        self.assertEqual(verify_plan.journey_proofs("| Goal | How it's proven |\n| Preserve edits | Reload |\n"), [])

    def test_tables_and_sources_parse_as_written(self):
        rows = verify_plan.journey_proofs("| Goal | How it's proven |\n| --- | --- |\n| Preserve A \\| B | |\n| Save | `e2e/a.spec.ts` |\n")
        self.assertEqual(rows, [('Preserve A | B', ''), ('Save', '`e2e/a.spec.ts`')])
        parsed = verify_plan.parse_standards(
            '| **Dimension** | **Source of truth** | **How changes are checked** |\n| --- | --- | --- |\n'
            '| Brand | `./docs/brand.md#voice` | Rubric |\n'
            '| Conventions | `Makefile` and `LICENSE` | CI |\n'
            '| Accessibility | none: owner deferred `WCAG2.2` | Later |\n'
            '| Escape | `../outside.md` | x |\n'
            '| Pipes | `docs/a.md` | checks A \\| B |\n'
            '| Spaces | `docs/Brand Guide.md#voice` | Rubric |\n')
        self.assertEqual(sorted(parsed), ['Accessibility', 'Brand', 'Conventions', 'Escape', 'Pipes', 'Spaces'])
        self.assertEqual(parsed['Spaces']['paths'], ['docs/Brand Guide.md'])
        self.assertEqual(parsed['Brand']['paths'], ['docs/brand.md'])
        self.assertEqual(parsed['Conventions']['paths'], ['Makefile', 'LICENSE'])
        self.assertEqual((parsed['Accessibility']['paths'], parsed['Accessibility']['none']), ([], 'owner deferred `WCAG2.2`'))
        self.assertEqual(parsed['Escape']['paths'], ['!../outside.md'])
        self.assertEqual(parsed['Pipes']['check'], 'checks A | B')
        # A source written with ./ is the same file the plan sees, so it is still always reviewed.
        config = {**CONFIG, '_standards': ['README.md']}
        self.assertEqual(verify_plan.plan(['README.md'], config)['unmapped'], ['README.md'])
        self.assertEqual(verify_plan.source_path('./README.md#brand'), 'README.md')

    def test_audit_asks_each_screen_feature_for_a_proven_journey(self):
        root = Path(tempfile.mkdtemp())
        (root / 'docs').mkdir()
        (root / 'docs/briefs.md').write_text('| Goal | How it\'s proven |\n| --- | --- |\n| Saves survive reload | `e2e/a.spec.ts` |\n'
                                             '| Empty state explains next step | |\n')
        config = {'static': ['docs/**'], 'suites': {'e2e': {'run': 'true', 'minutes': 1, 'target': 'app'}},
                  'targets': {'app': {'url': 'http://x', 'ready': 'http://x', 'auth': 'none'}},
                  'features': {'briefs': {'paths': ['app/briefs/**'], 'suites': ['e2e'], 'journey': 'docs/briefs.md'},
                               'auth': {'paths': ['app/auth/**'], 'suites': ['e2e']},
                               'cli': {'paths': ['cli/**'], 'journey': 'docs/missing.md'}}}
        files = ['app/briefs/a.ts', 'app/auth/a.ts', 'cli/x.py', 'docs/briefs.md']
        text = '\n'.join(f'{level}: {t}' for level, t in verify_plan.audit(files, config, root))
        self.assertIn('WARN: Feature auth has screens but no "outcome" document', text)
        self.assertIn('FAIL: Feature cli names outcome docs/missing.md, which is not a tracked file', text)
        self.assertIn('WARN: Outcome docs/briefs.md does not say how these are proven: Empty state explains next step', text)
        # "outcome" is the field's name; "journey" is still read.
        config['features']['auth']['outcome'] = 'docs/briefs.md'
        text = '\n'.join(f'{level}: {t}' for level, t in verify_plan.audit(files, config, root))
        self.assertNotIn('Feature auth has screens but no', text)
        self.assertNotIn('Feature briefs has screens but no', text)

    def test_status_follows_verdict_at_current_head(self):
        self.assertIn('failure: No verdict', self.run_script('check', '--pr', '5', code=1))
        self.verdict()
        self.assertIn('success: Verified', self.run_script('check', '--pr', '5'))
        self.write(files=['app/briefs/save.ts'], head='b' * 40)
        self.assertIn('No verdict for head bbbbbbb', self.run_script('check', '--pr', '5', code=1))
        self.run_script('check', '--pr', '5', '--set-status')
        status = json.loads(self.state.read_text())['statuses'][-1]
        self.assertEqual((status['state'], status['context']), ('failure', 'jfactory verified'))

    def set_ci(self, *runs):
        db = json.loads(self.state.read_text())
        db['check_runs'] = {'check_runs': [dict(zip(('name', 'status', 'conclusion'), r)) for r in runs]}
        self.state.write_text(json.dumps(db))

    def test_verified_verdict_relies_on_green_ci_at_the_head(self):
        # The verifier reuses CI results instead of re-running suites, so they must be complete and passing.
        self.set_ci()
        self.assertIn('No CI check has run', self.verdict(code=2))
        self.set_ci(('checks', 'in_progress', None))
        self.assertIn('CI is still running', self.verdict(code=2))
        self.set_ci(('checks', 'completed', 'failure'), ('status', 'completed', 'success'))
        self.assertIn('CI did not pass at aaaaaaa (checks)', self.verdict(code=2))
        # A failed verdict can always be posted; the gate's own job is not CI evidence.
        self.run_script('verdict', '--pr', '5', '--head', HEAD, '--verdict', 'failed', '--cause', 'change', '--verifier', 'codex/gpt-6-sol',
                        '--implementer', 'claude/opus-5-5-1m', '--evidence', 'x')
        self.set_ci(('checks', 'completed', 'success'), ('lint', 'completed', 'skipped'), ('status', 'in_progress', None))
        self.verdict()
        self.assertIn('success: Verified', self.run_script('check', '--pr', '5'))

    def test_status_counts_a_verdict_only_while_ci_is_green(self):
        self.verdict()
        self.assertIn('success: Verified', self.run_script('check', '--pr', '5'))
        # A later CI failure at the same head (or a verdict comment written by hand) no longer passes.
        self.set_ci(('checks', 'completed', 'failure'))
        self.assertIn('failure: CI did not pass at aaaaaaa', self.run_script('check', '--pr', '5', code=1))
        db = json.loads(self.state.read_text())
        db['check_runs'] = 'not json'
        self.state.write_text(json.dumps(db))
        self.assertIn('needs `checks: read`', self.run_script('check', '--pr', '5', code=1))

    def test_reverification_after_a_fix_checks_only_the_changes_since(self):
        self.run_script('verdict', '--pr', '5', '--head', HEAD, '--verdict', 'failed', '--cause', 'change', '--verifier', 'codex/gpt-6-sol',
                        '--implementer', 'claude/opus-5-5-1m', '--evidence', 'x')
        fixed = 'c' * 40
        self.write(files=['app/briefs/save.ts'], head=fixed)
        self.assertIn('No earlier verdict at bbbbbbb', self.verdict('--since', 'b' * 40, head=fixed, code=2))
        out = self.verdict('--since', HEAD, head=fixed)
        body = json.loads(self.state.read_text())['prs']['5']['comments'][-1]['body']
        self.assertIn('Re-checked the changes since the verdict at `aaaaaaa`', body)
        self.assertIn('success: Verified', self.run_script('check', '--pr', '5'))
        # A forged `since` pointing at a head with no verdict does not count.
        db = json.loads(self.state.read_text())
        db['prs']['5']['comments'] = [c for c in db['prs']['5']['comments'] if '"failed"' not in c['body']]
        self.state.write_text(json.dumps(db))
        self.assertIn('which has no earlier verdict', self.run_script('check', '--pr', '5', code=1))

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
        self.write(files=['lint/rules.py'])
        self.assertIn('success: Low-risk change', self.run_script('check', '--pr', '5'))
        self.write(files=['lint/rules.test.py'])
        self.assertIn('No verdict', self.run_script('check', '--pr', '5', code=1))
        self.write(files=['lint/rules.py', 'app/briefs/save.ts'])
        self.assertIn('No verdict', self.run_script('check', '--pr', '5', code=1))
        self.verdict('--features', 'briefs')
        self.assertIn('success: Verified', self.run_script('check', '--pr', '5'))

    def test_non_static_pr_must_state_its_objective(self):
        self.write(files=['lint/rules.py'])
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

    def failing(self, verdict='failed', *extra, code=0):
        return self.run_script('verdict', '--pr', '5', '--head', HEAD, '--verdict', verdict, '--verifier',
                               'codex/gpt-6-sol', '--implementer', 'claude/opus-5-5-1m', '--evidence', 'https://ev',
                               *extra, code=code)

    def last_record(self):
        body = json.loads(self.state.read_text())['prs']['5']['comments'][-1]['body']
        return json.loads(verify_plan.VERDICT_RE.search(body).group(1)), body

    def rule_issues(self):
        return {k: v for k, v in json.loads(self.state.read_text()).get('issues', {}).items()
                if {'name': verify_plan.RULE_CHANGE_LABEL} in v['labels']}

    def test_failed_and_blocked_verdicts_name_their_cause(self):
        for verdict in ('failed', 'blocked'):
            self.assertIn(f'A {verdict} verdict needs --cause', self.failing(verdict, code=2))
        self.assertIn('applies only to failed or blocked', self.verdict('--cause', 'change', code=2))
        self.assertIn('applies only to failed or blocked',
                      self.failing('partially-verified', '--cause', 'rules', '--rule-change', RULE, code=2))
        self.assertIn('--cause rules needs --rule-change', self.failing('failed', '--cause', 'rules', code=2))
        self.assertIn('--cause rules needs --rule-change', self.failing('blocked', '--cause', 'both', code=2))
        self.assertIn("must name the rule's file", self.failing(
            'failed', '--cause', 'rules', '--rule-change', 'the model rule is stale and should go', code=2))
        self.assertIn("must name the rule's file", self.failing(
            'failed', '--cause', 'rules', '--rule-change', 'references/models.md', code=2))
        self.assertIn('needs --cause rules or both', self.failing('failed', '--cause', 'change', '--rule-change', RULE,
                                                                  code=2))
        self.assertEqual(json.loads(self.state.read_text())['prs']['5']['comments'], [])
        self.failing('failed', '--cause', 'change')
        record, body = self.last_record()
        self.assertEqual(record['cause'], 'change')
        self.assertNotIn('rule_changes', record)
        self.assertIn('**Cause: the change (fix the PR and re-verify)**', body)
        self.assertEqual(self.rule_issues(), {})
        self.assertIn('Latest verdict at aaaaaaa is failed', self.run_script('check', '--pr', '5', code=1))

    def test_a_rules_verdict_asks_the_owner_once_per_pr_and_still_blocks(self):
        out = self.failing('failed', '--cause', 'rules', '--rule-change', RULE)
        self.assertIn('Opened rule-change issue', out)
        record, body = self.last_record()
        self.assertEqual((record['cause'], record['rule_changes']), ('rules', [RULE]))
        self.assertIn('Cause: the rules', body)
        self.assertIn(f'- {RULE}', body)
        # The gate stays honest: a rules failure blocks merging like any other until the owner decides.
        self.assertIn("is failed (cause: rules; waiting on the owner's decision",
                      self.run_script('check', '--pr', '5', code=1))
        issues = self.rule_issues()
        self.assertEqual(len(issues), 1)
        issue = next(iter(issues.values()))
        self.assertEqual(issue['title'], 'Rule change needed for PR #5')
        for part in (RULE, 'Change the rule as proposed', 'Keep the rule', 'aaaaaaa'):
            self.assertIn(part, issue['body'])
        self.assertIn(verify_plan.RULE_CHANGE_LABEL, json.loads(self.state.read_text())['labels'])
        # A second rules verdict on the same PR updates the issue instead of opening another, even once closed.
        self.assertIn('Updated rule-change issue #1', self.failing('blocked', '--cause', 'both', '--rule-change', RULE))
        db = json.loads(self.state.read_text())
        db['issues']['1']['state'] = 'CLOSED'
        self.state.write_text(json.dumps(db))
        self.failing('failed', '--cause', 'rules', '--rule-change', RULE)
        issues = self.rule_issues()
        self.assertEqual((len(issues), issues['1']['state'], len(issues['1']['comments'])), (1, 'OPEN', 2))
        self.failing('failed', '--cause', 'both', '--rule-change', RULE)
        self.assertIn('fix the change, and the owner decides', self.run_script('check', '--pr', '5', code=1))
        self.assertEqual(len(self.rule_issues()['1']['comments']), 3)
        # Inside a program the coordinator raises the owner decision instead, so no issue is opened.
        self.assertIn('Program #9 records this', self.failing('failed', '--cause', 'rules', '--rule-change', RULE,
                                                              '--program', '9'))
        self.assertEqual(len(self.rule_issues()['1']['comments']), 3)
        # No agent waives the rule: verifying afterwards needs a link to the owner's decision.
        self.assertIn('Only the owner settles that', self.verdict(code=2))
        self.assertIn('must link the owner', self.verdict('--rule-decision', 'owner said ok', code=2))
        self.verdict('--rule-decision', 'https://github.test/issues/1#issuecomment-1')
        self.assertIn('success: Verified', self.run_script('check', '--pr', '5'))
        # A verified record written without the decision does not count either.
        db = json.loads(self.state.read_text())
        record, _ = self.last_record()
        record.pop('rule_decision')
        db['prs']['5']['comments'][-1]['body'] = f'<!-- jfactory-verdict {json.dumps(record)} -->'
        self.state.write_text(json.dumps(db))
        self.assertIn("said a rule is wrong; this verdict must link the owner's decision",
                      self.run_script('check', '--pr', '5', code=1))

    def test_a_fix_after_a_rules_verdict_also_links_the_decision(self):
        self.failing('failed', '--cause', 'rules', '--rule-change', RULE)
        fixed = 'c' * 40
        self.write(files=['app/briefs/save.ts'], head=fixed)
        self.assertIn('Only the owner settles that', self.verdict('--since', HEAD, head=fixed, code=2))
        self.verdict('--since', HEAD, '--rule-decision', 'https://github.test/issues/1#c2', head=fixed)
        self.assertIn('success: Verified', self.run_script('check', '--pr', '5'))

    def test_an_unresolved_rule_finding_survives_later_heads_and_verdicts(self):
        # The verifier's three bypasses: a new head without --since, and an intervening change-cause or partial verdict.
        newer = 'c' * 40
        for between in ([], ['failed', '--cause', 'change'], ['partially-verified']):
            self.write(files=['app/briefs/save.ts'])
            self.failing('failed', '--cause', 'rules', '--rule-change', RULE)
            if between:
                self.failing(*between)
            self.write(files=['app/briefs/save.ts'], head=newer)
            self.assertIn('Only the owner settles that', self.verdict(head=newer, code=2), between)
            # A hand-posted verified record is rejected by the status too.
            db = json.loads(self.state.read_text())
            record = {'head': newer, 'verdict': 'verified', 'features': ['briefs'], 'full': False,
                      'verifier': 'codex/gpt-6.1-sol', 'implementer': 'claude/opus-5-5-1m', 'evidence': ['x']}
            db['prs']['5']['comments'].append({'authorAssociation': 'OWNER',
                                               'body': f'<!-- jfactory-verdict {json.dumps(record)} -->'})
            self.state.write_text(json.dumps(db))
            self.assertIn("said a rule is wrong", self.run_script('check', '--pr', '5', code=1), between)
        # The owner's decision settles it; later verdicts need no new link until a new rules finding.
        self.verdict('--rule-decision', 'https://github.test/issues/1#c2', head=newer)
        self.assertIn('success: Verified', self.run_script('check', '--pr', '5'))

    def test_the_rule_issue_is_found_beyond_the_first_page_of_labelled_issues(self):
        db = json.loads(self.state.read_text())
        issues = db.setdefault('issues', {})
        # GitHub lists newest first, so this PR's old issue comes after 258 newer labelled issues.
        for n in range(2, 260):
            issues[str(n)] = {'title': f'Rule change needed for PR #{1000 + n}', 'url': f'https://github.test/issues/{n}',
                              'state': 'OPEN', 'comments': [], 'labels': [{'name': 'jfactory-rule-change'}]}
        issues['1'] = {'title': 'Rule change needed for PR #5', 'url': 'https://github.test/issues/1', 'state': 'CLOSED', 'comments': [],
                       'labels': [{'name': 'jfactory-rule-change'}]}
        self.state.write_text(json.dumps(db))
        self.failing('failed', '--cause', 'rules', '--rule-change', RULE)
        db = json.loads(self.state.read_text())
        self.assertEqual(len([i for i in db['issues'].values() if i['title'] == 'Rule change needed for PR #5']), 1)
        self.assertEqual(db['issues']['1']['state'], 'OPEN')

    def test_old_verdicts_without_a_cause_still_evaluate(self):
        old = {'head': HEAD, 'verdict': 'failed', 'features': ['briefs'], 'full': False, 'verifier': 'codex/gpt-6-sol',
               'implementer': 'claude/opus-5-5-1m', 'evidence': ['x']}
        self.assertEqual(verify_plan.verdict_cause(old), 'change')
        self.assertIsNone(verify_plan.verdict_cause({**old, 'verdict': 'verified'}))
        db = json.loads(self.state.read_text())
        db['prs']['5']['comments'] = [{'authorAssociation': 'OWNER',
                                       'body': f'<!-- jfactory-verdict {json.dumps(old)} -->'}]
        self.state.write_text(json.dumps(db))
        out = self.run_script('check', '--pr', '5', code=1)
        self.assertIn('Latest verdict at aaaaaaa is failed', out)
        self.assertNotIn('cause', out)
        # An old failed verdict reads as a change failure: the next verdict needs no owner decision.
        self.verdict()
        self.assertIn('success: Verified', self.run_script('check', '--pr', '5'))

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
        if code is not None:
            self.assertEqual(proc.returncode, code, proc.stdout + proc.stderr)
        return proc.stdout + proc.stderr

    def change(self, path):
        (self.root / path).parent.mkdir(parents=True, exist_ok=True)
        (self.root / path).write_text('changed\n')
        self.git('add', '-A')
        self.git('commit', '-qm', 'change')

    def ran(self):
        return sorted(p.name for p in self.root.glob('ran-*'))

    def test_full_suite_command_reads_the_owners_choice(self):
        self.assertEqual(self.run_script('full-suite', '--event', 'schedule').strip(), 'mode=full')
        self.write_config(full_suite='on-request')
        self.assertEqual(self.run_script('full-suite', '--event', 'schedule').strip(), 'mode=skip')
        self.assertEqual(self.run_script('full-suite', '--event', 'pull_request', '--labels', 'bug').strip(), 'mode=planned')
        self.assertEqual(self.run_script('full-suite', '--event', 'pull_request', '--labels', 'bug,full-suite').strip(),
                         'mode=full')
        # JSON keeps label names exact: a label containing a comma is one label.
        self.assertEqual(self.run_script('full-suite', '--event', 'pull_request',
                                         '--labels-json', '["bug,full-suite"]').strip(), 'mode=planned')
        self.write_config(full_suite='on-request', full_suite_label='release,full')
        self.assertEqual(self.run_script('full-suite', '--event', 'pull_request',
                                         '--labels-json', '["release,full"]').strip(), 'mode=full')
        self.assertEqual(self.run_script('full-suite', '--event', 'push', '--labels-json', 'null').strip(), 'mode=skip')
        self.assertIn('JSON array', self.run_script('full-suite', '--event', 'pull_request', '--labels-json', '{"a": 1}',
                                                    code=2))

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

    def test_live_model_suites_never_gate_a_pr_and_run_only_with_live(self):
        live = {'run': 'touch ran-live', 'minutes': 3, 'live_model': True}
        self.write_config(suites={**self.config['suites'], 'agent-cli': live},
                          features={**self.config['features'],
                                    'cli': {'paths': ['cli/**'], 'suites': ['unit', 'cli', 'agent-cli']}})
        self.change('cli/run.py')
        out = self.run_script('ci', '--base', 'main')
        self.assertEqual(self.ran(), ['ran-cli', 'ran-unit'])
        self.assertIn('Live-model suites, not run on this PR', out)
        self.assertNotIn('agent-cli', out.split('CI suites:')[1].splitlines()[0])
        self.run_script('ci', '--all')
        self.assertNotIn('ran-live', self.ran(), 'A whole-suite run is still a gate; live suites stay off it')
        for marker in self.root.glob('ran-*'):
            marker.unlink()
        self.run_script('ci', '--live')
        self.assertEqual(self.ran(), ['ran-live'])
        self.write_config(suites={**self.config['suites'], 'agent-cli': live}, always_suites=['unit', 'agent-cli'])
        self.assertIn('never gate a PR', self.run_script('audit', code=None))

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

    def test_each_run_gets_its_own_test_data_and_removes_it(self):
        data = self.root / 'data'
        local = {**self.config['targets']['local'],
                 'seed': 'mkdir -p data && echo brief > data/$JFACTORY_RUN_ID',
                 'cleanup': 'rm -f data/$JFACTORY_RUN_ID', 'prune': 'rm -rf data && touch pruned'}
        suites = {**self.config['suites'], 'browser-briefs': {
            'run': 'test "$(ls data)" = "$JFACTORY_RUN_ID" && touch ran-browser', 'minutes': 2, 'target': 'local'}}
        self.write_config(targets={'local': local}, suites=suites)
        (self.root / '.gitignore').write_text('ran-*\nimpact/\ndata/\npruned\n')
        self.change('app/briefs/a.py')
        # The journey sees only its own record, and the record is gone afterwards.
        self.run_script('ci', '--base', 'HEAD~1')
        self.assertEqual((self.ran(), list(data.iterdir())), (['ran-browser', 'ran-unit'], []))
        # Cleanup still runs when the journey fails.
        failing = {**suites, 'browser-briefs': {**suites['browser-briefs'], 'run': 'exit 4'}}
        self.write_config(targets={'local': local}, suites=failing)
        (self.root / 'app/briefs/a.py').write_text('changed again\n')
        self.git('add', '-A')
        self.git('commit', '-qm', 'second change')
        self.run_script('ci', '--base', 'HEAD~1', code=1)
        self.assertEqual(list(data.iterdir()), [])
        # A leftover from an interrupted run is removed by the nightly prune.
        (data / 'jf-old').write_text('brief')
        for marker in self.root.glob('ran-*'):
            marker.unlink()
        self.write_config(targets={'local': local}, suites=suites)
        self.assertIn('prune local: done', self.run_script('ci', '--all'))
        self.assertTrue((self.root / 'pruned').exists())
        self.assertEqual(self.ran(), ['ran-browser', 'ran-cli', 'ran-unit'])
        self.assertEqual(list(data.iterdir()), [])

    def test_audit_warns_when_journeys_share_one_accounts_data(self):
        items = verify_plan.audit(['app/briefs/a.py', 'cli/run.py', 'README.md', '.gitignore'], self.config)
        self.assertTrue(any(level == 'WARN' and 'no "seed" and "cleanup"' in text for level, text in items), items)

    def test_smoke_records_a_receipt_and_reports_the_failed_step(self):
        out = self.run_script('smoke', '--target', 'local', '--fresh', '--record', '.jfactory/smoke.json')
        self.assertIn('Target local is ready', out)
        receipt = json.loads((self.root / '.jfactory' / 'smoke.json').read_text())['local']
        self.assertEqual((receipt['ok'], receipt['fresh'], [s['step'] for s in receipt['steps']]),
                         (True, True, ['doctor', 'ready', 'probe']))
        self.write_config(targets={'local': {**self.config['targets']['local'], 'doctor': 'echo missing DATABASE_URL; exit 2'}})
        out = self.run_script('smoke', '--target', 'local', '--record', '.jfactory/smoke.json', code=1)
        self.assertIn('FAIL: doctor', out)
        self.assertIn('a setup failure', out)
        self.assertNotIn('Retrying', out, 'A setup failure fails the same way every time')
        receipt = json.loads((self.root / '.jfactory' / 'smoke.json').read_text())['local']
        self.assertEqual((receipt['ok'], receipt['failure']), (False, 'setup'))
        self.write_config(targets={'local': {**self.config['targets']['local'], 'start': 'sleep 30'}})
        out = self.run_script('smoke', '--target', 'local', '--timeout', '2', code=1)
        self.assertIn('did not answer within 2s', out)
        self.assertIn('an environment failure, and again after 1 retry', out)
        self.assertEqual(out.count('FAIL: ready'), 2, 'Both attempts are reported')

    def test_smoke_retries_an_environment_failure_once_and_records_both_attempts(self):
        # The probe fails on the first attempt only, as a briefly unavailable service would.
        self.write_config(targets={'local': {**self.config['targets']['local'],
                                             'probe': 'test -e probed || { touch probed; exit 7; }'}})
        out = self.run_script('smoke', '--target', 'local', '--record', '.jfactory/smoke.json')
        self.assertIn('Retrying: probe failed', out)
        self.assertIn('Target local is ready', out)
        receipt = json.loads((self.root / '.jfactory' / 'smoke.json').read_text())['local']
        self.assertEqual([(s['step'], s['ok'], s.get('attempt')) for s in receipt['steps']],
                         [('doctor', True, None), ('ready', True, 1), ('probe', False, 1), ('ready', True, None),
                          ('probe', True, None)])
        (self.root / 'probed').unlink()
        self.run_script('smoke', '--target', 'local', '--retries', '0', code=1)
