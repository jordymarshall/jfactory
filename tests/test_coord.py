import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COORD = ROOT / 'skills' / 'jfactory' / 'scripts' / 'coord.py'
FAKE = ROOT / 'tests' / 'fakes' / 'fake_cli.py'
BRIEF = '\n'.join(f'{field} filled in' for field in [
    'OBJECTIVE', 'DECISIONS', 'SCOPE', 'CONTEXT', 'ACCEPTANCE', 'VERIFY', 'SHARED', 'LIMITS', 'FORBIDDEN',
    'DELIVERY', 'REPORT'])


class CoordTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.state = self.tmp / 'fake.json'
        self.state.write_text(json.dumps({'prs': {}}))
        bins = self.tmp / 'bin'
        bins.mkdir()
        for tool in ('gh', 'conductor', 'git'):
            exe = bins / tool
            exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKE}" {tool} "$@"\n')
            exe.chmod(0o755)
        self.env = {**os.environ, 'FAKE_STATE': str(self.state), 'JFACTORY_GH': str(bins / 'gh'),
                    'JFACTORY_CONDUCTOR': str(bins / 'conductor'), 'JFACTORY_GIT': str(bins / 'git')}
        self.brief = self.tmp / 'brief.md'
        self.brief.write_text(BRIEF)

    def coord(self, *args, ok=True):
        proc = subprocess.run([sys.executable, str(COORD), '--repo', 'o/r', *args], cwd=self.tmp,
                              env=self.env, capture_output=True, text=True)
        if ok:
            self.assertEqual(proc.returncode, 0, proc.stderr)
        else:
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        return proc.stdout + proc.stderr

    def db(self):
        return json.loads(self.state.read_text())

    def program_state(self):
        body = self.db()['issues']['1']['body']
        return json.loads(body.split('<!-- jfactory-program\n')[1].split('\n-->')[0])

    def set_db(self, **values):
        db = self.db()
        db.update(values)
        self.state.write_text(json.dumps(db))

    def start(self, *units, limit=2):
        self.coord('init', '--title', 'Two features', '--limit', str(limit), '--merge-deploys', 'staging')
        for unit in units:
            self.coord('add', '1', *unit, *([] if '--requires' in unit else ['--requires', 'unit']))

    def test_launch_uses_policy_and_tells_worker_how_to_report(self):
        self.start(['a', '--objective', 'Save items'])
        self.assertIn('| a | planned | implement: claude/opus-5-5-1m |', self.db()['issues']['1']['body'])
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        workspace = self.db()['workspaces'][0]
        self.assertEqual((workspace['agent'], workspace['model'], workspace['effort'], workspace['fast'],
                          workspace['branch']), ('claude', 'opus-5-5-1m', 'medium', False, 'main'))
        command = next(line.strip() for line in workspace['message'].splitlines() if '--state in-review' in line)
        self.assertIn('--repo o/r report 1 a --state in-review', command)
        # The printed command must parse exactly as a worker would run it.
        argv = command.split(' ', 2)[2].replace('<number>', '7').replace('<sha>', 'abc').split()
        argv = [a.strip('"') for a in argv][:9]
        self.coord(*argv[2:])
        self.assertIn('owner decision', workspace['message'])
        self.assertEqual(self.db()['section'], 'Program: Two features')
        self.assertEqual(self.db()['moves'], [['sec1'], ['w1', 'sec1']])
        unit = self.program_state()['units']['a']
        self.assertEqual((unit['state'], unit['session'], unit['attempts']), ('running', 's1', 1))

    def test_refuses_incomplete_brief_limit_dependency_hold_and_unknown_model(self):
        self.start(['a', '--objective', 'x'], ['b', '--objective', 'y'], ['c', '--objective', 'z', '--depends', 'a'],
                   limit=1)
        partial = self.tmp / 'partial.md'
        partial.write_text('OBJECTIVE only this\n')
        self.assertIn('missing: DECISIONS', self.coord('launch', '1', 'a', '--brief', str(partial), ok=False))
        self.assertIn('not offered', self.coord('launch', '1', 'a', '--brief', str(self.brief), '--model', 'nope',
                                                ok=False))
        self.assertIn('Dependencies not merged', self.coord('launch', '1', 'c', '--brief', str(self.brief), ok=False))
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        self.assertIn('limit 1 reached', self.coord('launch', '1', 'b', '--brief', str(self.brief), ok=False))
        db = self.db()
        db['issues']['1']['labels'].append({'name': 'jfactory-hold'})
        self.state.write_text(json.dumps(db))
        self.assertIn('on hold', self.coord('launch', '1', 'b', '--brief', str(self.brief), ok=False))
        self.assertIn('PROGRAM ON HOLD', self.coord('report', '1', 'a', '--state', 'running'))
        self.assertEqual(len(self.db()['workspaces']), 1)

    def test_worker_report_sync_verdict_and_merge_gate_on_current_head(self):
        self.start(['a', '--objective', 'x', '--requires', 'application'])
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        self.set_db(prs={'7': {'state': 'OPEN', 'headRefOid': 'aaa1111', 'headRefName': 'feat/a'}})
        self.coord('report', '1', 'a', '--state', 'in-review', '--pr', '7', '--head', 'aaa1111', '--note', 'done')
        self.assertIn('worker reported in-review', self.coord('sync', '1'))
        self.assertIn('no verified verdict', self.coord('merge', '1', 'a', ok=False))
        self.assertIn('not bbb2222', self.coord('verdict', '1', 'a', '--head', 'bbb2222', '--verdict', 'verified',
                                                '--scopes', 'application', '--evidence', 'x', '--verifier', 'codex/gpt-6-sol', ok=False))
        self.coord('verdict', '1', 'a', '--head', 'aaa1111', '--verdict', 'verified', '--scopes', 'application',
                   '--evidence', 'https://evidence', '--verifier', 'codex/gpt-6-sol')
        self.set_db(prs={'7': {'state': 'OPEN', 'headRefOid': 'ccc3333', 'headRefName': 'feat/a'}})
        self.assertIn('voids its verdict', self.coord('sync', '1'))
        self.assertIn('no verified verdict', self.coord('merge', '1', 'a', ok=False))
        self.coord('verdict', '1', 'a', '--head', 'ccc3333', '--verdict', 'verified', '--scopes', 'application',
                   '--evidence', 'https://evidence', '--verifier', 'codex/gpt-6-sol')
        self.coord('merge', '1', 'a')
        self.assertEqual(self.db()['merged'], ['7'])
        self.assertIn('jfactory-verdict', self.db()['prs']['7']['comments'][-1]['body'])
        merge_call = [c for c in self.db()['calls'] if c[1:3] == ['pr', 'merge']][0]
        self.assertIn('ccc3333', merge_call)

    def test_worker_question_becomes_gate_that_blocks_merge_until_resolved(self):
        self.start(['a', '--objective', 'x'])
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        self.set_db(prs={'7': {'state': 'OPEN', 'headRefOid': 'aaa1111', 'headRefName': 'feat/a'}})
        self.coord('report', '1', 'a', '--state', 'blocked', '--pr', '7', '--head', 'aaa1111',
                   '--question', 'Grid or list?')
        self.assertIn('parked as G1', self.coord('sync', '1'))
        self.coord('verdict', '1', 'a', '--head', 'aaa1111', '--verdict', 'verified', '--scopes', 'unit',
                   '--evidence', 'x', '--verifier', 'codex/gpt-6-sol')
        self.assertIn('G1', self.coord('merge', '1', 'a', ok=False))
        self.coord('gate', 'resolve', '1', '--id', 'G1', '--answer', 'Grid')
        self.coord('merge', '1', 'a')

    def test_review_needs_other_family_and_retries_are_capped(self):
        self.start(['a', '--objective', 'x', '--effort', 'high'],
                   ['r', '--objective', 'verify a', '--role', 'verify', '--depends', 'a', '--effort', 'low'], limit=3)
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        self.set_db(prs={'7': {'state': 'MERGED', 'headRefOid': 'aaa1111', 'headRefName': 'feat/a'}})
        self.coord('report', '1', 'a', '--state', 'in-review', '--pr', '7', '--head', 'aaa1111')
        self.coord('sync', '1')
        self.assertEqual(self.db()['workspaces'][0]['effort'], 'high')
        self.assertIn('same agent family', self.coord('launch', '1', 'r', '--brief', str(self.brief), '--agent',
                                                      'claude', '--model', 'opus-5-5-1m', ok=False))
        self.coord('launch', '1', 'r', '--brief', str(self.brief))
        verifier = self.db()['workspaces'][-1]
        self.assertEqual((verifier['agent'], verifier['model'], verifier['effort'], verifier['fast']),
                         ('codex', 'gpt-6-luna', 'low', True))
        for _ in range(2):
            self.coord('set', '1', 'r', '--state', 'failed')
            self.coord('launch', '1', 'r', '--brief', str(self.brief))
        self.coord('set', '1', 'r', '--state', 'failed')
        self.assertIn('abandon it and replan', self.coord('launch', '1', 'r', '--brief', str(self.brief), ok=False))

    def test_stale_report_does_not_override_coordinator_and_close_requires_terminal_units(self):
        self.start(['a', '--objective', 'x'])
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        db = self.db()
        report = {'unit': 'a', 'state': 'running', 'at': '2000-01-01T00:00:00Z'}
        db['issues']['1']['comments'].append({'body': f'<!-- jfactory-report {json.dumps(report)} -->',
                                              'createdAt': '2000-01-01T00:00:00Z'})
        self.state.write_text(json.dumps(db))
        self.coord('set', '1', 'a', '--state', 'abandoned', '--note', 'replanned')
        self.coord('sync', '1')
        self.assertEqual(self.program_state()['units']['a']['state'], 'abandoned')
        self.coord('add', '1', 'b', '--objective', 'y', '--requires', 'static')
        self.assertIn('not merged, done or abandoned: b', self.coord('close', '1', ok=False))
        self.coord('set', '1', 'b', '--state', 'done', '--note', 'verifier finished')
        self.coord('close', '1')
        self.assertEqual(self.db()['issues']['1']['state'], 'CLOSED')

    def test_verifier_is_done_not_merged_when_its_target_merges(self):
        self.start(['a', '--objective', 'x'], ['r', '--objective', 'verify a', '--role', 'verify', '--depends', 'a'],
                   limit=3)
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        self.set_db(prs={'7': {'state': 'OPEN', 'headRefOid': 'aaa1111', 'headRefName': 'feat/a'}})
        self.coord('report', '1', 'a', '--state', 'in-review', '--pr', '7', '--head', 'aaa1111')
        self.coord('sync', '1')
        self.coord('launch', '1', 'r', '--brief', str(self.brief), '--stack-on', 'a')
        self.coord('report', '1', 'r', '--state', 'in-review', '--pr', '7', '--head', 'aaa1111')
        self.set_db(prs={'7': {'state': 'MERGED', 'headRefOid': 'aaa1111', 'headRefName': 'feat/a'}})
        self.coord('sync', '1')
        units = self.program_state()['units']
        self.assertEqual((units['a']['state'], units['r']['state']), ('merged', 'done'))
        self.coord('close', '1')

    def test_open_decision_and_unsupported_fast_mode_block_launch(self):
        self.start(['a', '--objective', 'x'], ['v', '--objective', 'verify', '--role', 'verify'], limit=3)
        self.coord('gate', 'add', '1', '--question', 'Grid or list?', '--options', 'grid,list', '--default', 'grid',
                   '--units', 'a')
        self.assertIn('Open owner decisions block a: G1', self.coord('launch', '1', 'a', '--brief', str(self.brief),
                                                                     ok=False))
        self.assertIn('does not support fast mode', self.coord('launch', '1', 'v', '--brief', str(self.brief),
                                                               '--model', 'gpt-5.6-sol', ok=False))
        self.assertNotIn('workspaces', self.db())

    def test_fallback_needs_a_reason_and_verifier_switches_family_after_codex_implementation(self):
        self.start(['a', '--objective', 'x'], ['r', '--objective', 'verify a', '--role', 'verify', '--depends', 'a'],
                   limit=3)
        self.assertIn('needs --reason', self.coord('launch', '1', 'a', '--brief', str(self.brief), '--fallback',
                                                   ok=False))
        self.coord('launch', '1', 'a', '--brief', str(self.brief), '--fallback', '--reason', 'Claude weekly 95%')
        worker = self.db()['workspaces'][-1]
        self.assertEqual((worker['agent'], worker['model'], worker['fast']), ('codex', 'gpt-6-astra', False))
        self.assertIn('fallback: Claude weekly 95%', self.program_state()['units']['a']['note'])
        self.set_db(prs={'7': {'state': 'OPEN', 'headRefOid': 'aaa1111', 'headRefName': 'feat/a'}})
        self.coord('report', '1', 'a', '--state', 'in-review', '--pr', '7', '--head', 'aaa1111')
        self.coord('sync', '1')
        self.coord('launch', '1', 'r', '--brief', str(self.brief), '--stack-on', 'a')
        verifier = self.db()['workspaces'][-1]
        self.assertEqual((verifier['agent'], verifier['model'], verifier['effort'], verifier['fast']),
                         ('claude', 'opus-5-5-1m', 'low', False))

    def test_verifier_fallback_holds_rather_than_verify_opus_work_with_opus(self):
        self.start(['a', '--objective', 'x'], ['r', '--objective', 'verify a', '--role', 'verify', '--depends', 'a'],
                   limit=3)
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        self.set_db(prs={'7': {'state': 'OPEN', 'headRefOid': 'aaa1111', 'headRefName': 'feat/a'}})
        self.coord('report', '1', 'a', '--state', 'in-review', '--pr', '7', '--head', 'aaa1111')
        self.coord('sync', '1')
        self.assertIn('same agent family', self.coord('launch', '1', 'r', '--brief', str(self.brief), '--stack-on', 'a',
                                                      '--fallback', '--reason', 'Codex weekly 95%', ok=False))

    def test_opus_verifier_effort_stays_low_even_when_requested_higher(self):
        self.start(['a', '--objective', 'x'], ['r', '--objective', 'verify a', '--role', 'verify', '--depends', 'a',
                                                '--effort', 'high'], limit=3)
        self.coord('launch', '1', 'a', '--brief', str(self.brief), '--fallback', '--reason', 'Claude weekly 95%')
        self.set_db(prs={'7': {'state': 'OPEN', 'headRefOid': 'aaa1111', 'headRefName': 'feat/a'}})
        self.coord('report', '1', 'a', '--state', 'in-review', '--pr', '7', '--head', 'aaa1111')
        self.coord('sync', '1')
        for override in (['--effort', 'high'], ['--agent', 'claude', '--model', 'opus-5-5-1m', '--effort', 'max']):
            self.assertIn('low effort only', self.coord('launch', '1', 'r', '--brief', str(self.brief), '--stack-on',
                                                        'a', *override, ok=False))
        self.coord('launch', '1', 'r', '--brief', str(self.brief), '--stack-on', 'a')
        verifier = self.db()['workspaces'][-1]
        self.assertEqual((verifier['agent'], verifier['model'], verifier['effort']), ('claude', 'opus-5-5-1m', 'low'))

    def test_effort_outside_policy_is_refused(self):
        self.start(['a', '--objective', 'x'])
        self.assertIn('outside the implement policy', self.coord('add', '1', 'b', '--objective', 'y', '--effort', 'max',
                                                                 '--requires', 'unit', ok=False))
        self.assertIn('outside the implement policy', self.coord('launch', '1', 'a', '--brief', str(self.brief),
                                                                 '--effort', 'max', ok=False))

    def test_verified_needs_required_scopes_and_merge_needs_non_production_target(self):
        self.coord('init', '--title', 'Prod merges')
        self.assertIn('--requires must name', self.coord('add', '1', 'a', '--objective', 'x', ok=False))
        self.coord('add', '1', 'a', '--objective', 'x', '--requires', 'application,unit')
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        self.set_db(prs={'7': {'state': 'OPEN', 'headRefOid': 'aaa1111', 'headRefName': 'feat/a'}})
        self.coord('report', '1', 'a', '--state', 'in-review', '--pr', '7', '--head', 'aaa1111')
        self.coord('sync', '1')
        self.assertIn('requires application evidence', self.coord('verdict', '1', 'a', '--head', 'aaa1111', '--verdict',
                                                               'verified', '--scopes', 'unit', '--evidence', 'x',
                                                               '--verifier', 'codex/gpt-6-sol', ok=False))
        self.coord('verdict', '1', 'a', '--head', 'aaa1111', '--verdict', 'verified', '--scopes', 'unit,application',
                   '--evidence', 'x', '--verifier', 'codex/gpt-6-sol')
        self.assertIn('unrecorded target', self.coord('merge', '1', 'a', ok=False))
        self.assertNotIn('merged', self.db())
        self.assertIn('deploys to: **unknown**', self.db()['issues']['1']['body'])

    def test_merge_refuses_a_production_target(self):
        self.coord('init', '--title', 'Prod', '--merge-deploys', 'production')
        self.coord('add', '1', 'a', '--objective', 'x', '--requires', 'unit')
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        self.set_db(prs={'7': {'state': 'OPEN', 'headRefOid': 'aaa1111', 'headRefName': 'feat/a'}})
        self.coord('report', '1', 'a', '--state', 'in-review', '--pr', '7', '--head', 'aaa1111')
        self.coord('sync', '1')
        self.coord('verdict', '1', 'a', '--head', 'aaa1111', '--verdict', 'verified', '--scopes', 'unit',
                   '--evidence', 'x', '--verifier', 'codex/gpt-6-sol')
        self.assertIn('deploys to production', self.coord('merge', '1', 'a', ok=False))
        self.assertNotIn('merged', self.db())

    def test_repository_policy_override(self):
        (self.tmp / '.jfactory').mkdir()
        (self.tmp / '.jfactory' / 'coordination.json').write_text(json.dumps(
            {'limit': 5, 'merge_deploys': 'production', 'roles': {'implement': {'agent': 'codex', 'model': 'gpt-5.6-sol', 'effort': 'high',
                                                  'efforts': ['high']}}}))
        self.coord('init', '--title', 'Override')
        self.coord('add', '1', 'a', '--objective', 'x', '--requires', 'unit', '--effort', 'high')
        state = self.program_state()
        self.assertEqual((state['limit'], state['merge_deploys']), (5, 'production'))
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        self.assertEqual(self.db()['workspaces'][0]['model'], 'gpt-5.6-sol')


if __name__ == '__main__':
    unittest.main()
