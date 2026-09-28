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
        for tool in ('gh', 'conductor'):
            exe = bins / tool
            exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKE}" {tool} "$@"\n')
            exe.chmod(0o755)
        self.env = {**os.environ, 'FAKE_STATE': str(self.state), 'JFACTORY_GH': str(bins / 'gh'),
                    'JFACTORY_CONDUCTOR': str(bins / 'conductor')}
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
        self.coord('init', '--title', 'Two features', '--limit', str(limit))
        for unit in units:
            self.coord('add', '1', *unit)

    def test_launch_uses_policy_and_tells_worker_how_to_report(self):
        self.start(['a', '--objective', 'Save items'])
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        workspace = self.db()['workspaces'][0]
        self.assertEqual((workspace['agent'], workspace['model'], workspace['branch']), ('claude', 'opus-5-5-1m', 'main'))
        self.assertIn('report --repo o/r 1 a --state in-review', workspace['message'])
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
        self.start(['a', '--objective', 'x'])
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        self.set_db(prs={'7': {'state': 'OPEN', 'headRefOid': 'aaa1111', 'headRefName': 'feat/a'}})
        self.coord('report', '1', 'a', '--state', 'in-review', '--pr', '7', '--head', 'aaa1111', '--note', 'done')
        self.assertIn('worker reported in-review', self.coord('sync', '1'))
        self.assertIn('no verified verdict', self.coord('merge', '1', 'a', ok=False))
        self.assertIn('not bbb2222', self.coord('verdict', '1', 'a', '--head', 'bbb2222', '--verdict', 'verified',
                                                '--scopes', 'application', '--evidence', 'x', ok=False))
        self.coord('verdict', '1', 'a', '--head', 'aaa1111', '--verdict', 'verified', '--scopes', 'application',
                   '--evidence', 'https://evidence')
        self.set_db(prs={'7': {'state': 'OPEN', 'headRefOid': 'ccc3333', 'headRefName': 'feat/a'}})
        self.assertIn('voids its verdict', self.coord('sync', '1'))
        self.assertIn('no verified verdict', self.coord('merge', '1', 'a', ok=False))
        self.coord('verdict', '1', 'a', '--head', 'ccc3333', '--verdict', 'verified', '--scopes', 'application',
                   '--evidence', 'https://evidence')
        self.coord('merge', '1', 'a')
        self.assertEqual(self.db()['merged'], ['7'])
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
                   '--evidence', 'x')
        self.assertIn('G1', self.coord('merge', '1', 'a', ok=False))
        self.coord('gate', 'resolve', '1', '--id', 'G1', '--answer', 'Grid')
        self.coord('merge', '1', 'a')

    def test_review_needs_other_family_and_retries_are_capped(self):
        self.start(['a', '--objective', 'x'], ['r', '--objective', 'review a', '--role', 'review', '--depends', 'a'],
                   limit=3)
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        self.set_db(prs={'7': {'state': 'MERGED', 'headRefOid': 'aaa1111', 'headRefName': 'feat/a'}})
        self.coord('report', '1', 'a', '--state', 'in-review', '--pr', '7', '--head', 'aaa1111')
        self.coord('sync', '1')
        self.assertIn('same agent family', self.coord('launch', '1', 'r', '--brief', str(self.brief), '--agent',
                                                      'claude', '--model', 'sonnet-5-1m', '--effort', 'medium',
                                                      ok=False))
        self.coord('launch', '1', 'r', '--brief', str(self.brief))
        self.assertEqual(self.db()['workspaces'][-1]['agent'], 'codex')
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
        self.coord('add', '1', 'b', '--objective', 'y')
        self.assertIn('not merged or abandoned: b', self.coord('close', '1', ok=False))
        self.coord('set', '1', 'b', '--state', 'abandoned')
        self.coord('close', '1')
        self.assertEqual(self.db()['issues']['1']['state'], 'CLOSED')

    def test_repository_policy_override(self):
        (self.tmp / '.jfactory').mkdir()
        (self.tmp / '.jfactory' / 'coordination.json').write_text(json.dumps(
            {'limit': 5, 'roles': {'implement': {'agent': 'codex', 'model': 'gpt-5.6-sol', 'effort': 'high'}}}))
        self.start(['a', '--objective', 'x'], limit=0)
        state = self.program_state()
        self.assertEqual(state['limit'], 5)
        self.coord('launch', '1', 'a', '--brief', str(self.brief))
        self.assertEqual(self.db()['workspaces'][0]['model'], 'gpt-5.6-sol')


if __name__ == '__main__':
    unittest.main()
