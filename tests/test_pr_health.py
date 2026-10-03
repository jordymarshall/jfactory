import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills' / 'jfactory' / 'scripts' / 'pr_health.py'
FAKE = ROOT / 'tests' / 'fakes' / 'fake_cli.py'
NOW = '2026-10-03T12:00:00Z'
HEAD = 'a' * 40


def check(name, conclusion='SUCCESS', status='COMPLETED', job=None, at='2026-10-03T10:00:00Z', workflow='CI'):
    return {'__typename': 'CheckRun', 'name': name, 'status': status, 'conclusion': conclusion,
            'workflowName': workflow, 'startedAt': at, 'completedAt': at if status == 'COMPLETED' else '0001-01-01T00:00:00Z',
            'detailsUrl': f'https://github.com/o/r/actions/runs/{job or 9}00/job/{job or 9}'}


def gate(state):
    return {'__typename': 'StatusContext', 'context': 'jfactory verified', 'state': state,
            'startedAt': '2026-10-03T10:00:00Z'}


def verdict(kind='verified', head=HEAD, evidence='Walkthrough done\nmore', at='2026-10-03T10:30:00Z', **extra):
    record = {'head': head, 'verdict': kind, 'evidence': [evidence], **extra}
    return {'authorAssociation': 'OWNER', 'createdAt': at, 'body': f'<!-- jfactory-verdict {json.dumps(record)} -->'}


def pr(number, rollup=None, comments=None, merge='BLOCKED', auto=None, draft=False, head=HEAD):
    return {'number': number, 'title': f'PR {number}', 'isDraft': draft, 'headRefOid': head, 'mergeStateStatus': merge,
            'autoMergeRequest': auto, 'createdAt': '2026-10-03T00:30:00Z', 'comments': comments or [],
            'statusCheckRollup': [check('checks')] + [gate('PENDING')] if rollup is None else rollup}


class PrHealthTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.state = self.tmp / 'fake.json'
        bins = self.tmp / 'bin'
        bins.mkdir()
        exe = bins / 'gh'
        exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKE}" gh "$@"\n')
        exe.chmod(0o755)
        self.env = {**os.environ, 'FAKE_STATE': str(self.state), 'JFACTORY_GH': str(exe)}
        self.write({'prs': {}, 'pr_list': [], 'jobs': {}})

    def write(self, db):
        self.state.write_text(json.dumps(db))

    def db(self):
        return json.loads(self.state.read_text())

    def set(self, **changes):
        db = self.db()
        db.update(changes)
        self.write(db)

    def run_tool(self, *args, now=NOW, code=0):
        proc = subprocess.run([sys.executable, str(SCRIPT), '--repo', 'o/r', '--now', now, *args],
                              env=self.env, capture_output=True, text=True)
        self.assertEqual(proc.returncode, code, proc.stdout + proc.stderr)
        return proc.stdout + proc.stderr

    def row(self, out, number):
        return next((line for line in out.splitlines() if line.startswith(f'| #{number} ')), None)

    def test_classifies_each_state(self):
        old = '2026-10-03T01:00:00Z'
        self.set(pr_list=[
            pr(1, merge='DIRTY'),
            pr(2, [check('checks', status='IN_PROGRESS'), gate('PENDING')]),
            pr(3),  # green 2 h ago, no verdict
            pr(4, comments=[verdict('partially-verified', evidence='Screens not walked: brief said keep it cheap')]),
            pr(5, [check('checks'), gate('SUCCESS')], comments=[verdict()], merge='CLEAN',
               auto={'mergeMethod': 'SQUASH'}),
            pr(6, [check('checks', at=old), gate('SUCCESS')], merge='CLEAN'),
            pr(7, [check('checks', status='QUEUED', at=old)]),
            pr(8, [check('checks'), gate('FAILURE')], comments=[verdict()]),
            pr(9, comments=[verdict()], merge='BEHIND'),
            pr(10, merge='BEHIND'),
            pr(11, draft=True, merge='DIRTY'),
            pr(12, [check('checks', at='2026-10-03T11:50:00Z'), gate('PENDING')]),
            pr(13, comments=[verdict('failed', cause='change', evidence='The button is missing')]),
            pr(14, [gate('PENDING')]),
        ])
        out = self.run_tool()
        expect = {1: 'conflict', 3: 'needs-verdict', 4: 'partial', 6: 'not-queued', 7: 'idle', 8: 'gate-failed',
                  9: 'behind', 10: 'behind', 13: 'partial', 14: 'no-ci'}
        for number, state in expect.items():
            self.assertIn(f'| {state} |', self.row(out, number) or '', number)
        # Quiet states, drafts and young PRs are not reported.
        for number in (2, 5, 11, 12):
            self.assertIsNone(self.row(out, number), number)
        self.assertIn('Screens not walked: brief said keep it cheap', self.row(out, 4))
        self.assertNotIn('more', self.row(out, 4))
        self.assertIn('Author: fix what the verifier found', self.row(out, 13))
        self.assertIn('Author: merge the base branch', self.row(out, 10))
        self.assertIn('would merge the base branch into the PR (dry run)', out)
        # A dry run changes nothing.
        db = self.db()
        self.assertFalse(db.get('updates') or db.get('reruns') or db.get('issues'))
        self.assertFalse([c for c in db['calls'] if c[1:3] in (['issue', 'create'], ['issue', 'edit'])])

    def test_updates_a_verified_behind_pr_once_per_head(self):
        self.set(pr_list=[pr(9, comments=[verdict()], merge='BEHIND')])
        out = self.run_tool('--act')
        self.assertIn('#9: merged the base branch into the PR', out)
        self.assertEqual(self.db()['updates'], [['repos/o/r/pulls/9/update-branch', f'expected_head_sha={HEAD}']])
        self.assertIn('Issue: opened', out)
        # GitHub has not moved the head yet: the next run does not ask again.
        out = self.run_tool('--act')
        self.assertEqual(len(self.db()['updates']), 1)
        self.assertIn('already requested', self.row(out, 9))
        # A new head that is verified and behind again gets one new update.
        self.set(pr_list=[pr(9, comments=[verdict(head='b' * 40)], merge='BEHIND', head='b' * 40)])
        self.run_tool('--act')
        self.assertEqual(len(self.db()['updates']), 2)
        # The record keeps only open heads.
        body = self.db()['issues']['1']['body']
        self.assertIn('update:9:' + 'b' * 40, body)
        self.assertNotIn('update:9:' + HEAD, body)

    def test_reruns_only_infrastructure_failures_once_per_head(self):
        jobs = {'1': {'steps': [{'name': 'Set up job', 'conclusion': 'success', 'started_at': 'x'},
                                {'name': 'Run tests', 'conclusion': 'failure', 'started_at': 'x'}]},
                '2': {'steps': []},
                '3': {'steps': [{'name': 'Set up job', 'conclusion': 'success', 'started_at': 'x'},
                                {'name': 'Run tests', 'conclusion': 'cancelled', 'started_at': 'x'}]},
                '4': {'steps': [{'name': 'Set up job', 'conclusion': 'success', 'started_at': 'x'},
                                {'name': 'Run tests', 'conclusion': 'cancelled', 'started_at': 'x'}]},
                '5': {'steps': [{'name': 'Run tests', 'conclusion': 'failure', 'started_at': 'x'}]}}
        notes = {'3': [{'message': 'The self-hosted runner: m1 lost communication with the server.'}],
                 '4': [{'message': 'The job running on runner m1 has exceeded the maximum execution time of 30 minutes.'}]}
        self.set(jobs=jobs, annotations=notes, pr_list=[
            pr(21, [check('unit', 'FAILURE', job=1), gate('PENDING')]),             # a test failed
            pr(22, [check('unit', 'FAILURE', job=2), gate('PENDING')]),             # the job never ran a step
            pr(23, [check('unit', 'FAILURE', job=3), gate('PENDING')]),             # runner lost
            pr(24, [check('unit', 'TIMED_OUT', job=4), gate('PENDING')]),           # a hung test timed out
            pr(25, [check('unit', 'CANCELLED', job=5), gate('PENDING')]),           # a failed step wins over cancelled
            pr(26, [check('unit', 'CANCELLED', job=2), check('lint', 'FAILURE', job=1), gate('PENDING')]),
        ])
        out = self.run_tool('--act')
        self.assertEqual(sorted(r[0] for r in self.db()['reruns']), ['200', '300'])
        self.assertTrue(all(r[1:] == ['--failed', '--repo', 'o/r'] for r in self.db()['reruns']))
        for number in (21, 24, 25, 26):
            self.assertIn('Author: fix the failing check', self.row(out, number), number)
        self.assertIn('step "Run tests" failed', self.row(out, 21))
        self.assertIn('lost communication', self.row(out, 23))
        # The same failure at the same head is not re-run again; the report asks a person instead.
        out = self.run_tool('--act')
        self.assertEqual(len(self.db()['reruns']), 2)
        self.assertIn('again after one re-run', self.row(out, 22))

    def test_one_issue_is_edited_in_place_closed_and_reopened(self):
        self.set(pr_list=[pr(1, merge='DIRTY')])
        self.assertIn('Issue: opened', self.run_tool('--act'))
        self.assertIn('jfactory-pr-health', self.db()['labels'])
        self.assertIn('Issue: updated', self.run_tool('--act', now='2026-10-03T13:00:00Z'))
        issue = self.db()['issues']['1']
        self.assertEqual(issue['title'], 'Stuck PRs')
        self.assertIn('| #1 PR 1 | conflict |', issue['body'])
        self.set(pr_list=[pr(5, [check('checks'), gate('SUCCESS')], merge='CLEAN', auto={'mergeMethod': 'SQUASH'})])
        self.assertIn('Issue: closed', self.run_tool('--act'))
        self.assertEqual(self.db()['issues']['1']['state'], 'CLOSED')
        self.assertIn('No stuck PRs.', self.db()['issues']['1']['body'])
        self.assertIn('Issue: closed already', self.run_tool('--act'))
        self.set(pr_list=[pr(1, merge='DIRTY')])
        self.assertIn('Issue: reopened', self.run_tool('--act'))
        db = self.db()
        self.assertEqual(len(db['issues']), 1)
        self.assertEqual(db['issues']['1']['state'], 'OPEN')
        # It never comments.
        self.assertEqual(db['issues']['1']['comments'], [])
        self.assertFalse([c for c in db['calls'] if c[1:3] == ['issue', 'comment']])

    def test_nothing_stuck_and_no_issue_creates_nothing(self):
        out = self.run_tool('--act')
        self.assertIn('No stuck PRs.', out)
        self.assertIn('nothing stuck; no issue', out)
        self.assertEqual(self.db().get('issues', {}), {})

    def test_gh_failure_exits_2(self):
        # The job lookup fails, so the tool cannot tell a test failure from an infrastructure one.
        self.set(pr_list=[pr(21, [check('unit', 'FAILURE', job=77), gate('PENDING')])])
        self.assertIn('REFUSED', self.run_tool(code=2))


if __name__ == '__main__':
    unittest.main()
