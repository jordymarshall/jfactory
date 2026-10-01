import json
import os
import subprocess
import sys
import tempfile
import time
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
                    'JFACTORY_CONDUCTOR': str(bins / 'conductor'), 'JFACTORY_GIT': str(bins / 'git'),
                    'CONDUCTOR_WORKSPACE_ID': 'w-here'}
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
                          workspace['branch']), ('claude', 'opus-5-5-1m', 'medium', True, 'main'))
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

    def test_sync_archives_finished_workspaces_once_their_sessions_stop(self):
        self.start(['a', '--objective', 'x'], ['r', '--objective', 'verify a', '--role', 'verify', '--depends', 'a'],
                   ['b', '--objective', 'y'], limit=3)
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        self.coord('launch', '1', 'b', '--brief', str(self.brief))
        self.set_db(prs={'7': {'state': 'OPEN', 'headRefOid': 'aaa1111', 'headRefName': 'feat/a'}})
        self.coord('report', '1', 'a', '--state', 'in-review', '--pr', '7', '--head', 'aaa1111')
        self.coord('sync', '1')
        self.coord('launch', '1', 'r', '--brief', str(self.brief), '--stack-on', 'a')
        self.coord('report', '1', 'r', '--state', 'in-review', '--pr', '7', '--head', 'aaa1111')
        self.set_db(prs={'7': {'state': 'MERGED', 'headRefOid': 'aaa1111', 'headRefName': 'feat/a'}},
                    sessions={'s1': 'idle', 's3': 'working'})
        out = self.coord('sync', '1')
        self.assertEqual(self.db().get('archived'), ['w1'])
        self.assertIn('r: done but its session is still working', out)
        self.set_db(sessions={'s1': 'idle', 's3': 'idle'})
        self.coord('sync', '1')
        self.coord('sync', '1')
        self.assertEqual(self.db()['archived'], ['w1', 'w3'])
        units = self.program_state()['units']
        self.assertTrue(units['a']['archived'] and units['r']['archived'])
        self.assertNotIn('archived', units['b'])

    def test_keep_workspaces_and_dry_run_do_not_archive(self):
        self.start(['a', '--objective', 'x'])
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        self.set_db(prs={'7': {'state': 'MERGED', 'headRefOid': 'aaa1111', 'headRefName': 'feat/a'}},
                    sessions={'s1': 'idle'})
        self.coord('report', '1', 'a', '--state', 'in-review', '--pr', '7', '--head', 'aaa1111')
        self.coord('sync', '1', '--dry-run')
        self.coord('sync', '1', '--keep-workspaces')
        self.assertNotIn('archived', self.db())

    def test_close_archives_abandoned_work_and_deletes_the_section(self):
        self.start(['a', '--objective', 'x'])
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        self.set_db(sessions={'s1': 'idle'})
        self.coord('set', '1', 'a', '--state', 'abandoned', '--note', 'superseded')
        out = self.coord('close', '1')
        self.assertEqual(self.db()['archived'], ['w1'])
        self.assertEqual(self.db()['deleted_sections'], ['sec1'])
        self.assertIn('coordinator workspace stays open', out)
        self.assertEqual(self.db()['issues']['1']['state'], 'CLOSED')

    def test_close_keeps_its_section_when_an_idle_workspace_fails_to_archive(self):
        self.start(['a', '--objective', 'x'])
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        self.coord('set', '1', 'a', '--state', 'abandoned')
        self.set_db(sessions={'s1': 'idle'}, archive_fail=['w1'],
                    sections=[{'id': 'sec1', 'name': 'Program: Two features', 'workspaceIds': ['w1']}])
        out = self.coord('close', '1')
        self.assertIn('workspace not archived', out)
        self.assertNotIn('deleted_sections', self.db())

    def test_sync_reports_status_and_archive_failures_without_crashing(self):
        self.start(['a', '--objective', 'x'], ['b', '--objective', 'y'], ['c', '--objective', 'z'], limit=3)
        for uid in ('a', 'b', 'c'):
            self.coord('launch', '1', uid, '--brief', str(self.brief))
        self.coord('set', '1', 'b', '--state', 'abandoned')
        self.coord('set', '1', 'c', '--state', 'abandoned')
        self.set_db(sessions={'s1': 'unavailable', 's2': 'unavailable', 's3': 'idle'}, archive_fail=['w3'])
        out = self.coord('sync', '1')
        self.assertIn('a: session status unavailable', out)
        self.assertIn('b: workspace not archived; session status unavailable', out)
        self.assertIn('c: workspace not archived', out)
        self.assertNotIn('archived', self.db())
        units = self.program_state()['units']
        self.assertFalse(units['b'].get('archived') or units['c'].get('archived'))

    def test_tidy_deletes_only_finished_program_sections(self):
        self.start(['a', '--objective', 'x'])
        self.set_db(archived=['w9'], issues={**self.db()['issues'], '2': {
            'title': 'Program: Old pilot', 'state': 'CLOSED', 'url': 'u', 'body': '', 'comments': []}},
            sections=[{'id': 'old', 'name': 'Program: Old pilot', 'workspaceIds': ['live-coordinator']},
                      {'id': 'empty', 'name': 'Program: Abandoned idea', 'workspaceIds': ['w9']},
                      {'id': 'live', 'name': 'Program: Two features', 'workspaceIds': ['w1']},
                      {'id': 'mine', 'name': 'Personal', 'workspaceIds': []}])
        self.set_db(sections=self.db()['sections'] + [
            {'id': 'busy', 'name': 'Program: Old pilot', 'workspaceIds': ['w7']}], sessions={'s7': 'working'})
        out = self.coord('tidy')
        self.assertEqual(self.db()['deleted_sections'], ['old', 'empty'])
        self.assertIn("'Program: Old pilot' (program closed)", out)
        self.assertIn("'Program: Abandoned idea' (no active workspaces)", out)
        self.coord('tidy')
        self.assertEqual(self.db()['deleted_sections'], ['old', 'empty'])

    def test_close_keeps_section_while_a_finished_session_is_still_working(self):
        self.start(['a', '--objective', 'x'])
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        self.coord('set', '1', 'a', '--state', 'abandoned')
        self.set_db(sections=[{'id': 'sec1', 'name': 'Program: Two features', 'workspaceIds': ['w1']}])
        out = self.coord('close', '1')
        self.assertEqual(self.db()['issues']['1']['state'], 'CLOSED')
        self.coord('tidy')
        self.assertNotIn('archived', self.db())
        self.assertNotIn('deleted_sections', self.db())
        self.assertIn('still working', out)

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
                   ['r', '--objective', 'verify a', '--role', 'verify', '--depends', 'a'], limit=3)
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
                         ('codex', 'gpt-6.1-sol', 'low', True))
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
        # Verify runs in fast mode by default; a model without fast mode in Conductor's catalog is refused.
        (self.tmp / '.jfactory').mkdir(exist_ok=True)
        (self.tmp / '.jfactory' / 'coordination.json').write_text(json.dumps({'roles': {'verify': {'fast': True}}}))
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

    def test_verifier_effort_stays_low_whatever_is_requested(self):
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

    def test_partial_role_override_keeps_the_rest_of_the_role(self):
        (self.tmp / '.jfactory').mkdir()
        (self.tmp / '.jfactory' / 'coordination.json').write_text(json.dumps(
            {'merge_deploys': 'none', 'roles': {'implement': {'effort': 'high'}, 'verify': {'efforts': ['low']}}}))
        self.coord('init', '--title', 'Partial')
        self.coord('add', '1', 'a', '--objective', 'x', '--requires', 'unit')
        self.coord('launch', '1', 'a', '--brief', str(self.brief), '--fallback', '--reason', 'Claude weekly 95%')
        worker = self.db()['workspaces'][-1]
        self.assertEqual((worker['agent'], worker['model'], worker['effort']), ('codex', 'gpt-6-astra', 'high'))
        (self.tmp / '.jfactory' / 'coordination.json').write_text(json.dumps({'roles': {'new': {'effort': 'low'}}}))
        self.assertIn('needs an agent and a model', self.coord('init', '--title', 'Broken', ok=False))

    def test_fast_and_trivial_roles_follow_their_tiers(self):
        self.start(['copy', '--objective', 'Fix a label', '--role', 'trivial', '--effort', 'low'],
                   ['ci', '--objective', 'Fix a known CI failure', '--role', 'fast'], limit=3)
        self.coord('launch', '1', 'copy', '--brief', str(self.brief))
        self.coord('launch', '1', 'ci', '--brief', str(self.brief), '--fallback', '--reason', 'Codex weekly 95%')
        trivial, fast = self.db()['workspaces']
        self.assertEqual((trivial['agent'], trivial['model'], trivial['effort']), ('codex', 'gpt-6-luna', 'low'))
        self.assertEqual((fast['agent'], fast['model'], fast['effort']), ('claude', 'opus-5-5-1m', 'low'))

    def test_sync_offers_a_verifier_once_its_target_has_a_pr(self):
        self.start(['a', '--objective', 'x'], ['r', '--objective', 'verify a', '--role', 'verify', '--depends', 'a'],
                   limit=3)
        self.assertNotIn('r (--stack-on', self.coord('sync', '1'))
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        self.set_db(prs={'7': {'state': 'OPEN', 'headRefOid': 'aaa1111', 'headRefName': 'feat/a'}})
        self.coord('report', '1', 'a', '--state', 'in-review', '--pr', '7', '--head', 'aaa1111')
        self.assertIn('Ready to launch (3 free slots): r (--stack-on a)', self.coord('sync', '1'))

    def test_a_failed_verdict_blocks_even_a_low_risk_merge(self):
        self.start(['t', '--objective', 'Lint'])
        config = {'features': {'lint': {'paths': ['lint/**'], 'verify': 'ci'}}}
        self.coord('launch', '1', 't', '--brief', str(self.brief))
        self.set_db(prs={'7': {'state': 'OPEN', 'headRefOid': 'aaa1111', 'headRefName': 'feat/t', 'files': ['lint/x.py']}},
                    config=config)
        self.coord('report', '1', 't', '--state', 'in-review', '--pr', '7', '--head', 'aaa1111')
        self.coord('sync', '1')
        self.coord('verdict', '1', 't', '--head', 'aaa1111', '--verdict', 'failed', '--scopes', 'unit',
                   '--evidence', 'https://evidence', '--verifier', 'codex/gpt-6-sol')
        self.assertIn('has a failed verdict', self.coord('merge', '1', 't', ok=False))
        self.assertNotIn('merged', self.db())

    def test_verdict_passes_screenshots_for_screen_changes(self):
        self.start(['a', '--objective', 'x'])
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        config = {'suites': {'journey': {'run': 'true', 'target': 'app'}},
                  'targets': {'app': {'url': 'http://x', 'ready': 'http://x', 'auth': 'none'}},
                  'features': {'app': {'paths': ['src/**'], 'suites': ['journey']}}}
        self.set_db(prs={'7': {'state': 'OPEN', 'headRefOid': 'aaa1111', 'headRefName': 'feat/a', 'files': ['src/x.tsx']}},
                    config=config)
        self.coord('report', '1', 'a', '--state', 'in-review', '--pr', '7', '--head', 'aaa1111')
        self.coord('sync', '1')
        verdict = ('verdict', '1', 'a', '--head', 'aaa1111', '--verdict', 'verified', '--scopes', 'unit',
                   '--evidence', 'https://evidence', '--verifier', 'codex/gpt-6-sol')
        self.assertIn('touches screens users see', self.coord(*verdict, ok=False))
        self.assertIn('step by step', self.coord(*verdict, '--screenshots', 'https://shots/desktop.png', ok=False))
        self.coord(*verdict, '--screenshots', 'https://shots/desktop.png', '--screenshots', 'https://shots/mobile.png',
                   '--walkthrough', 'https://trail/desktop.html')
        self.assertIn('https://shots/mobile.png', self.db()['prs']['7']['comments'][-1]['body'])

    def test_verdict_needs_a_known_implementer(self):
        self.start(['a', '--objective', 'x'])
        self.set_db(prs={'7': {'state': 'OPEN', 'headRefOid': 'aaa1111', 'headRefName': 'feat/a'}})
        self.coord('report', '1', 'a', '--state', 'in-review', '--pr', '7', '--head', 'aaa1111')
        self.coord('sync', '1')
        self.assertIn('model family', self.coord('verdict', '1', 'a', '--head', 'aaa1111', '--verdict', 'verified',
                                                 '--scopes', 'unit', '--evidence', 'x', '--verifier',
                                                 'codex/gpt-6-luna', ok=False))

    def test_low_risk_unit_merges_on_ci_without_a_verdict(self):
        self.start(['t', '--objective', 'Add lint rules'], ['a', '--objective', 'Feature'])
        config = {'features': {'lint': {'paths': ['lint/**'], 'verify': 'ci'}, 'app': {'paths': ['src/**']}}}
        for unit, number, files in (('t', '7', ['lint/x.py']), ('a', '8', ['src/x.py', 'lint/x.py'])):
            self.coord('launch', '1', unit, '--brief', str(self.brief))
            prs = self.db()['prs']
            prs[number] = {'state': 'OPEN', 'headRefOid': f'{unit}' * 7, 'headRefName': f'feat/{unit}', 'files': files}
            self.set_db(prs=prs, config=config)
            self.coord('report', '1', unit, '--state', 'in-review', '--pr', number, '--head', f'{unit}' * 7)
        self.coord('sync', '1')
        self.coord('merge', '1', 't')
        self.assertIn('no verified verdict', self.coord('merge', '1', 'a', ok=False))
        self.assertEqual(self.db()['merged'], ['7'])


    # Workspaces launched for one PR are named <role>-<repo>-<pr> and archived once that PR is finished.

    def pr_workspace(self, wid, name, repo_url='https://github.com/o/r'):
        return {'id': wid, 'name': name, 'state': 'ready', 'repoUrl': repo_url, 'creatorName': 'Owner'}

    def test_tidy_archives_only_idle_convention_workspaces_whose_pr_finished(self):
        other = 'https://github.com/o/r-other'
        self.set_db(prs={'7': {'state': 'MERGED'}, '8': {'state': 'OPEN'}, '9': {'state': 'CLOSED'}},
                    listed=[self.pr_workspace('w-merged', 'verify-r-7'),
                            self.pr_workspace('w-closed', 'build-r-9', 'https://github.com/o/r.git'),
                            self.pr_workspace('w-busy', 'fix-r-7'),
                            self.pr_workspace('w-open', 'verify-r-8'),
                            self.pr_workspace('w-here', 'verify-r-7'),
                            self.pr_workspace('w-owner', 'Owner notes on r-7'),
                            self.pr_workspace('w-short', 'verify-lc-7'),
                            self.pr_workspace('w-review', 'review-r-7'),
                            self.pr_workspace('w-other', 'verify-r-7', other),
                            self.pr_workspace('w-othername', 'verify-r-other-7', other)],
                    sessions={**{s: 'idle' for s in ('s-merged', 's-closed', 's-open', 's-here', 's-owner', 's-short',
                                                     's-review', 's-other', 's-othername')}, 's-busy': 'working'})
        out = self.coord('tidy')
        self.assertEqual(self.db()['archived'], ['w-merged', 'w-closed'])
        self.assertIn('archived workspace verify-r-7 (PR #7 merged)', out)
        self.assertIn('fix-r-7 kept: PR #7 is merged but a session is still working', out)
        listing = next(c for c in self.db()['calls'] if c[1:3] == ['workspace', 'list'])
        self.assertIn('--mine', listing)
        self.set_db(sessions={'s-busy': 'idle'})
        self.coord('tidy')
        self.assertEqual(self.db()['archived'], ['w-merged', 'w-closed', 'w-busy'])

    def test_sync_verdict_merge_and_close_archive_finished_pr_workspaces(self):
        self.start(['a', '--objective', 'x'])
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        prs = {'7': {'state': 'OPEN', 'headRefOid': 'aaa1111', 'headRefName': 'feat/a'}}
        self.set_db(prs=prs, sessions={'s1': 'idle'})
        self.coord('report', '1', 'a', '--state', 'in-review', '--pr', '7', '--head', 'aaa1111')
        steps = [('sync', '1'),
                 ('verdict', '1', 'a', '--head', 'aaa1111', '--verdict', 'verified', '--scopes', 'unit',
                  '--evidence', 'https://evidence', '--verifier', 'codex/gpt-6.1-sol'),
                 ('merge', '1', 'a'),
                 ('close', '1')]
        for number, step in enumerate(steps, 20):
            prs = self.db()['prs']
            prs[str(number)] = {'state': 'MERGED'}
            if step[0] == 'close':
                prs['7']['state'] = 'MERGED'
            self.set_db(prs=prs, sessions={**self.db()['sessions'], f's-{number}': 'idle'},
                        listed=self.db().get('listed', []) + [self.pr_workspace(f'w-{number}', f'verify-r-{number}')])
            out = self.coord(*step)
            self.assertIn(f'w-{number}', self.db().get('archived', []), f'{step[0]} did not archive: {out}')
            self.assertIn(f'archived workspace verify-r-{number}', out)

    def test_missing_or_failing_conductor_never_fails_verdict_sync_or_merge(self):
        self.start(['a', '--objective', 'x'])
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        self.set_db(prs={'7': {'state': 'OPEN', 'headRefOid': 'aaa1111', 'headRefName': 'feat/a'},
                         '20': {'state': 'MERGED'}},
                    listed=[self.pr_workspace('w-20', 'verify-r-20')], sessions={'s-20': 'idle'})
        self.coord('report', '1', 'a', '--state', 'in-review', '--pr', '7', '--head', 'aaa1111')
        verdict = ('verdict', '1', 'a', '--head', 'aaa1111', '--verdict', 'verified', '--scopes', 'unit',
                   '--evidence', 'https://evidence', '--verifier', 'codex/gpt-6.1-sol')
        fake = self.env['JFACTORY_CONDUCTOR']
        self.env['JFACTORY_CONDUCTOR'] = str(self.tmp / 'no-such-conductor')
        for step in (('sync', '1'), verdict, ('merge', '1', 'a'), ('tidy',)):
            out = self.coord(*step)
            self.assertNotIn('Traceback', out)
            self.assertNotIn('finished workspaces not tidied', out)  # no conductor CLI: skipped quietly
        self.env['JFACTORY_CONDUCTOR'] = fake
        self.set_db(conductor_fail=True)
        for step in (('sync', '1'), verdict, ('merge', '1', 'a')):
            out = self.coord(*step)
            self.assertIn('finished workspaces not tidied', out)
        self.assertEqual(self.db()['merged'], ['7', '7'])
        self.assertEqual(len([c for c in self.db()['prs']['7']['comments'] if 'jfactory-verdict' in c['body']]), 2)
        self.assertNotIn('archived', self.db())

    def test_workspace_tidy_is_time_boxed(self):
        sys.path.insert(0, str(COORD.parent))
        import coord
        from unittest import mock
        self.set_db(conductor_sleep=5, prs={'7': {'state': 'MERGED'}},
                    listed=[self.pr_workspace('w-7', 'verify-r-7')], sessions={'s-7': 'idle'})
        with mock.patch.dict(os.environ, self.env):
            started = time.monotonic()
            archived, notes = coord.archive_merged('o/r', budget=1)
        self.assertLess(time.monotonic() - started, 4)
        self.assertEqual(archived, [])
        self.assertIn('timed out', ' '.join(notes))

    def test_launch_names_a_pr_workspace_by_convention(self):
        message = self.tmp / 'verify.md'
        message.write_text('Verify PR 7 at its head.')
        self.set_db(prs={'7': {'state': 'OPEN', 'headRefOid': 'aaa1111', 'headRefName': 'feat/a'}})
        out = self.coord('launch', '--role', 'verify', '--pr', '7', '--message-file', str(message))
        self.assertEqual(out.splitlines()[0], 'w1')
        workspace = self.db()['workspaces'][0]
        self.assertEqual((workspace['name'], workspace['branch'], workspace['agent'], workspace['model'],
                          workspace['effort'], workspace['fast'], workspace['repo_url'], workspace['project']),
                         ('verify-r-7', 'feat/a', 'codex', 'gpt-6.1-sol', 'low', True, 'https://github.com/o/r', None))
        self.set_db(projects=[{'id': 'p-other', 'gitRemote': 'https://github.com/o/r-other'},
                              {'id': 'p-r', 'gitRemote': 'https://github.com/o/r'}])
        self.coord('launch', '--role', 'fix', '--pr', '7', '--branch', 'feat/a', '--message-file', str(message))
        workspace = self.db()['workspaces'][1]
        self.assertEqual((workspace['name'], workspace['agent'], workspace['project'], workspace['repo_url']),
                         ('fix-r-7', 'claude', 'p-r', None))
        self.assertIn('--role must be one of verify, build, fix',
                      self.coord('launch', '--role', 'review', '--pr', '7', '--message-file', str(message), ok=False))
        self.assertIn('breaks the <role>-<repo>-<pr> convention',
                      self.coord('launch', '--role', 'verify', '--pr', '7', '--name', 'verify-lc-7',
                                 '--message-file', str(message), ok=False))
        self.assertIn('either', self.coord('launch', '1', 'a', '--role', 'verify', '--pr', '7', ok=False))
        self.assertEqual(len(self.db()['workspaces']), 2)

    # Negative controls from the failed verdict on #37 at 738a135: each case must keep the workspace.

    def test_a_working_session_on_a_later_page_keeps_the_workspace(self):
        # The server returns two sessions per page here, so the working one is on page two.
        many = ['s-many-0', 's-many-1', 's-many-2']
        idle = ['s-idle-0', 's-idle-1', 's-idle-2']
        self.set_db(prs={'7': {'state': 'MERGED'}, '8': {'state': 'MERGED'}}, page_size=2,
                    listed=[self.pr_workspace('w-many', 'verify-r-7'), self.pr_workspace('w-idle', 'verify-r-8')],
                    workspace_sessions={'w-many': many, 'w-idle': idle},
                    sessions={**{sid: 'idle' for sid in many + idle}, 's-many-2': 'working'})
        out = self.coord('tidy')
        self.assertEqual(self.db().get('archived'), ['w-idle'])
        self.assertIn('verify-r-7 kept: PR #7 is merged but a session is still working', out)
        offsets = [c[c.index('--offset') + 1] for c in self.db()['calls'] if c[1:3] == ['workspace', 'session']]
        self.assertEqual(offsets, ['0', '2', '0', '2'])

    def test_a_replayed_or_misnumbered_page_keeps_the_workspace(self):
        # The verifier's case: offset 1 returns page 0 again, then claims the list is complete.
        replayed = {'0': {'offset': 0, 'data': [{'id': 's-a'}], 'hasMore': True},
                    '1': {'offset': 0, 'data': [{'id': 's-a'}], 'hasMore': False}}
        repeated = {'0': {'offset': 0, 'data': [{'id': 's-b'}], 'hasMore': True},
                    '1': {'offset': 1, 'data': [{'id': 's-b'}], 'hasMore': False}}
        no_offset = {'0': {'data': [{'id': 's-c'}], 'hasMore': False}}
        self.set_db(prs={'7': {'state': 'MERGED'}, '8': {'state': 'MERGED'}, '9': {'state': 'MERGED'}},
                    listed=[self.pr_workspace('w-a', 'verify-r-7'), self.pr_workspace('w-b', 'verify-r-8'),
                            self.pr_workspace('w-c', 'verify-r-9')],
                    session_replies={'w-a': replayed, 'w-b': repeated, 'w-c': no_offset},
                    sessions={'s-a': 'idle', 's-b': 'idle', 's-c': 'idle'})
        out = self.coord('tidy')
        self.assertEqual(self.db().get('archived', []), [])
        self.assertIn('offset 0 for 1', out)
        self.assertIn('repeated items across pages', out)

    def test_repository_identity_is_exact_host_owner_and_name(self):
        wrong = ['https://gitlab.com/o/r', 'https://gitlab.com/github.com/o/r', 'https://github.com/x/o/r',
                 'https://github.com.evil.test/o/r', 'https://github.com/o/r/extra', 'git@gitlab.com:o/r.git',
                 'https://github.com/o/r-other', 'https://github.com/o', None]
        right = ['git@github.com:o/r.git', 'ssh://git@github.com/o/r', 'https://github.com/O/R/']
        listed = [self.pr_workspace(f'w-wrong-{i}', 'verify-r-7', url) for i, url in enumerate(wrong)]
        listed += [self.pr_workspace(f'w-right-{i}', 'verify-r-7', url) for i, url in enumerate(right)]
        self.set_db(prs={'7': {'state': 'MERGED'}}, listed=listed,
                    sessions={f"s-{w['id'][2:]}": 'idle' for w in listed})
        self.coord('tidy')
        self.assertEqual(self.db()['archived'], ['w-right-0', 'w-right-1', 'w-right-2'])
        # Project selection uses the same identity: a GitLab project listed first must not be chosen.
        message = self.tmp / 'm.md'
        message.write_text('Fix PR 7.')
        self.set_db(projects=[{'id': 'p-gitlab', 'gitRemote': 'https://gitlab.com/o/r'},
                              {'id': 'p-nested', 'gitRemote': 'https://gitlab.com/github.com/o/r'},
                              {'id': 'p-r', 'gitRemote': 'git@github.com:o/r.git'}])
        self.coord('launch', '--role', 'fix', '--pr', '7', '--branch', 'b', '--message-file', str(message))
        self.assertEqual(self.db()['workspaces'][-1]['project'], 'p-r')

    def test_only_an_idle_session_status_lets_a_workspace_go(self):
        replies = {'s-empty': '{}', 's-null': '{"status": null}', 's-unknown': '{"status": "unknown"}',
                   's-list': '[]', 's-text': 'not json'}
        listed = [self.pr_workspace(f'w-{kind[2:]}', f'verify-r-{n}') for n, kind in enumerate(replies, 7)]
        listed.append(self.pr_workspace('w-idle', 'verify-r-20'))
        self.set_db(prs={str(n): {'state': 'MERGED'} for n in range(7, 21)}, listed=listed, raw_status=replies,
                    sessions={'s-idle': 'idle'})
        out = self.coord('tidy')
        self.assertEqual(self.db()['archived'], ['w-idle'])
        for n, status in ((7, '{}'), (8, 'None'), (9, "'unknown'")):
            self.assertIn(f'verify-r-{n} kept', out)
        self.assertIn("s-unknown='unknown' does not show idle", out)
        # A malformed session list keeps the workspace too.
        self.set_db(listed=[self.pr_workspace('w-bad', 'verify-r-7')], workspace_sessions={'w-bad': [None]})
        self.assertIn('verify-r-7 kept', self.coord('tidy'))
        self.assertNotIn('w-bad', self.db()['archived'])

    def test_names_must_match_the_convention_exactly(self):
        near = ['verify-r-7\n', 'verify-r-7 ', ' verify-r-7', 'Verify-r-7', 'verify-r-07', 'verify-r-7-old',
                'verify-r-7\r', 'verify-r-', 'verify-r-7.']
        listed = [self.pr_workspace(f'w-near-{i}', name) for i, name in enumerate(near)]
        listed.append(self.pr_workspace('w-exact', 'verify-r-7'))
        listed.append(self.pr_workspace('w-case', 'fix-R-7'))  # repository names are case-insensitive on GitHub
        self.set_db(prs={'7': {'state': 'MERGED'}}, listed=listed,
                    sessions={f"s-{w['id'][2:]}": 'idle' for w in listed})
        self.coord('tidy')
        self.assertEqual(self.db()['archived'], ['w-exact', 'w-case'])

    def test_a_slow_conductor_cannot_hold_up_a_verdict(self):
        self.start(['a', '--objective', 'x'])
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        self.set_db(prs={'7': {'state': 'OPEN', 'headRefOid': 'aaa1111', 'headRefName': 'feat/a'}})
        self.coord('report', '1', 'a', '--state', 'in-review', '--pr', '7', '--head', 'aaa1111')
        self.coord('sync', '1')
        self.set_db(conductor_sleep=25)
        started = time.monotonic()
        out = self.coord('verdict', '1', 'a', '--head', 'aaa1111', '--verdict', 'verified', '--scopes', 'unit',
                         '--evidence', 'https://evidence', '--verifier', 'codex/gpt-6.1-sol')
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 12, out)
        self.assertIn('Posted verified verdict', out)
        self.assertIn('finished workspaces not tidied', out)

    def test_a_github_failure_is_reported_once_not_per_workspace(self):
        listed = [self.pr_workspace(f'w-{n}', f'verify-r-{n}') for n in range(1, 13)]
        self.set_db(prs={str(n): {'state': 'MERGED'} for n in range(1, 13)}, listed=listed, gh_fail=True,
                    sessions={f's-{n}': 'idle' for n in range(1, 13)})
        lines = [line for line in self.coord('tidy').splitlines() if 'verify-r-' in line or 'finished workspaces' in line]
        self.assertEqual(len(lines), 1, lines)
        self.assertIn('HTTP 502', lines[0])
        self.assertNotIn('archived', self.db())
        self.env['JFACTORY_GH'] = str(self.tmp / 'no-such-gh')
        lines = [line for line in self.coord('tidy').splitlines() if 'finished workspaces' in line]
        self.assertEqual(lines, ['Check: finished workspaces not tidied: gh is not installed or not on PATH'])

if __name__ == '__main__':
    unittest.main()
