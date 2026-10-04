import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HUB = ROOT / 'skills/jfactory/skills/agent-coordinator/scripts/hub.py'
COORD = ROOT / 'skills/jfactory/scripts/coord.py'
FAKE = ROOT / 'tests/fakes/fake_cli.py'
BRIEF = '\n'.join(f'{f} x' for f in ('OBJECTIVE', 'DECISIONS', 'SCOPE', 'CONTEXT', 'ACCEPTANCE', 'VERIFY', 'SHARED',
                                      'LIMITS', 'FORBIDDEN', 'DELIVERY', 'REPORT'))


class HubTest(unittest.TestCase):
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
        self.env.pop('CONDUCTOR_SESSION_ID', None)
        (self.tmp / 'brief.md').write_text(BRIEF)

    def tool(self, script, *args, session=None, code=0):
        env = {**self.env, **({'CONDUCTOR_SESSION_ID': session} if session else {})}
        proc = subprocess.run([sys.executable, str(script), '--repo', 'o/r', *args], cwd=self.tmp, env=env,
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, code, proc.stdout + proc.stderr)
        return proc.stdout + proc.stderr

    def hub(self, *args, **kw):
        return self.tool(HUB, *args, **kw)

    def coord(self, *args, **kw):
        return self.tool(COORD, *args, **kw)

    def db(self):
        return json.loads(self.state.read_text())

    def messages(self, session):
        return [m['text'] for m in self.db().get('messages', []) if m['session'] == session]

    def program(self, coordinator='coord-1'):
        """A program whose coordinator is `coordinator`, with one launched worker (session s1)."""
        self.coord('init', '--title', 'Library', '--limit', '2', '--merge-deploys', 'staging', session=coordinator)
        self.coord('add', '1', 'grid', '--objective', 'Grid', '--requires', 'unit', '--paths', 'app/library/**')
        self.coord('launch', '1', 'grid', '--brief', str(self.tmp / 'brief.md'))

    def hub_issue(self):
        return next(i for i in self.db()['issues'].values() if i['labels'][0]['name'] == 'jfactory-hub')

    def test_claim_registers_the_hub_pins_it_and_tells_every_coordinator(self):
        self.program()
        out = self.hub('claim', '--notify', session='hub-a')
        self.assertIn('Hub: hub-a', out)
        issue = self.hub_issue()
        self.assertTrue(issue.get('pinned'))
        self.assertIn('**Hub session:** `hub-a`', issue['body'])
        self.assertIn('Workers report to their coordinator, never to the hub', issue['body'])
        told = self.messages('coord-1')
        self.assertTrue(any('hub-a is now the hub' in m and 'QUESTION' in m for m in told), told)

    def test_a_second_claim_takes_over_and_the_old_hub_stops_relaying(self):
        self.program()
        self.hub('claim', '--notify', session='hub-a')
        self.hub('ledger', 'add', '--kind', 'question', '--text', 'Ship on Friday?', '--from', 'coord-1',
                 '--owner', 'coord-1', session='hub-a')
        out = self.hub('claim', '--notify', session='hub-b')
        self.assertIn('Took over from hub-a', out)
        self.assertTrue(any('HUB HANDOVER: hub-b' in m for m in self.messages('hub-a')))
        self.assertIn('You are no longer the hub; hub-b is', self.hub('check', session='hub-a', code=3))
        self.assertIn('You are the hub', self.hub('check', session='hub-b'))
        # The open question survives the take-over.
        self.assertIn('Ship on Friday?', self.hub('ledger', 'list'))

    def test_a_worker_is_redirected_to_its_coordinator(self):
        self.program()
        self.hub('claim', session='hub-a')
        out = self.hub('route', '--from', 's1', '--reply')
        self.assertIn('worker grid of #1', out)
        self.assertTrue(any('Workers do not message the hub' in m and 'coord-1' in m for m in self.messages('s1')))
        self.assertIn('coordinator of #1', self.hub('route', '--from', 'coord-1'))
        self.assertEqual(self.hub('route', '--from', 'stranger').strip(), 'unknown')

    def test_an_owner_answer_reaches_the_agent_that_owns_the_action(self):
        self.program()
        self.hub('claim', session='hub-a')
        item = self.hub('ledger', 'add', '--kind', 'question', '--text', 'Merge #12 now or after the release?',
                        '--from', 'coord-1', '--owner', 'coord-1').strip()
        self.assertEqual(item, 'H1')
        self.assertIn('| H1 | question | coord-1 |', self.hub_issue()['body'])
        self.assertIn('Relayed to coord-1', self.hub('ledger', 'resolve', 'H1', '--answer', 'After the release', '--relay'))
        self.assertTrue(any('ANSWER H1' in m and 'After the release' in m for m in self.messages('coord-1')))
        self.assertNotIn('Merge #12', self.hub('ledger', 'list'))
        self.assertIn('resolved', self.hub('ledger', 'list', '--all'))

    def test_a_hold_is_sent_to_the_agent_that_owns_the_action(self):
        self.program()
        self.hub('claim', session='hub-a')
        self.assertIn('needs --owner', self.hub('ledger', 'add', '--kind', 'hold', '--text', 'Do not merge #316', code=2))
        self.assertIn('Hold sent to coord-1',
                      self.hub('ledger', 'add', '--kind', 'hold', '--text', 'Do not merge #316', '--owner', 'coord-1'))
        self.assertTrue(any(m.startswith('HOLD from the agent hub') and '#316' in m for m in self.messages('coord-1')))

    def test_handoff_starts_a_new_session_that_inherits_every_open_item(self):
        self.program()
        self.hub('claim', session='hub-a')
        self.hub('ledger', 'add', '--kind', 'question', '--text', 'Q one', '--from', 'coord-1', '--owner', 'coord-1')
        self.hub('ledger', 'add', '--kind', 'risk', '--text', 'CI queue long', '--owner', 'coord-1')
        out = self.hub('handoff', '--create', '--workspace', 'w-here', '--reason', 'context', session='hub-a')
        self.assertIn('Hub: new-hub-1. Open items carried over: H1, H2', out)
        created = self.db()['created_sessions'][0]
        self.assertEqual(created['workspace'], 'w-here')
        self.assertIn('Read the ledger first', created['text'])
        self.assertIn('**Hub session:** `new-hub-1`', self.hub_issue()['body'])
        self.assertTrue(any('handed over from hub-a to new-hub-1' in m for m in self.messages('coord-1')))
        self.hub('check', session='hub-a', code=3)
        listed = self.hub('ledger', 'list')
        self.assertIn('Q one', listed)
        self.assertIn('CI queue long', listed)

    def test_status_builds_a_table_from_programs_and_the_ledger(self):
        self.program()
        self.hub('claim', session='hub-a')
        self.hub('ledger', 'add', '--kind', 'blocker', '--text', 'Lease busy', '--owner', 'coord-1', '--eta', '23:30')
        out = self.hub('status')
        self.assertIn('| Workstream | Status | Summary | ETA |', out)
        self.assertIn('| #1 Program: Library | active | 1 running |', out)
        self.assertIn('H1 BLOCKER: Lease busy (owner coord-1, ETA 23:30)', out)

    def test_without_conductor_coordinators_hear_through_their_program_issue(self):
        self.program(coordinator='coord-1')
        self.env['JFACTORY_CONDUCTOR'] = str(self.tmp / 'missing-conductor')
        self.hub('claim', '--notify', session='hub-a')
        comments = [c['body'] for c in self.db()['issues']['1']['comments']]
        self.assertTrue(any('hub-a is now the hub' in c for c in comments), comments)

    def test_coord_records_its_coordinator_and_routes_workers_and_coordinators(self):
        self.program(coordinator='coord-1')
        launch = next(w for w in self.db()['workspaces'] if w['name'].endswith('grid') or 'grid' in w['message'])
        self.assertIn('Never message the agent hub', launch['message'])
        self.hub('claim', session='hub-a')
        out = self.coord('sync', '1', session='coord-2')
        self.assertIn('Agent hub: hub-a', out)
        self.assertIn('workers never message it', out)
        self.assertIn('coordinator of #1', self.hub('route', '--from', 'coord-2'))


if __name__ == '__main__':
    unittest.main()
