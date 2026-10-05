import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/jfactory/scripts/usage.py'
MODELS = ROOT / 'skills/jfactory/references/models.md'

FAKE_CONDUCTOR = r'''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
state = Path(os.environ['FAKE_STATE'])
args = [a for a in sys.argv[1:] if a != '--json']
with open(state / 'calls.log', 'a') as log:
    log.write(' '.join(args) + '\n')
def events(sid):
    path = state / f'{sid}.json'
    return json.loads(path.read_text()) if path.exists() else []
if args[:2] == ['workspace', 'session']:
    print(json.dumps({'data': json.loads((state / 'sessions.json').read_text()), 'hasMore': False}))
elif args[:2] == ['session', 'message']:
    limit, offset = int(args[args.index('--limit') + 1]), int(args[args.index('--offset') + 1])
    data = events(args[2])
    print(json.dumps({'data': data[offset:offset + limit], 'offset': offset, 'hasMore': offset + limit < len(data)}))
elif args[:2] == ['session', 'create']:
    agent = args[args.index('--agent') + 1]
    probe = state / f'probe-{agent}.json'
    if agent == 'claude':
        (state / 'probe-claude-session.json').write_text(probe.read_text())
    else:
        target = Path(os.environ['CODEX_HOME']) / 'sessions' / 'rollout-probe.jsonl'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(probe.read_text())
    print(json.dumps({'id': f'probe-{agent}-session'}))
elif args[:2] == ['session', 'status']:
    print(json.dumps({'status': 'idle'}))
elif args[:2] == ['session', 'archive']:
    print('{}')
else:
    sys.exit(2)
'''

FAKE_CODEX = r'''#!/usr/bin/env python3
import json, os, sys
mode = os.environ.get('FAKE_CODEX', 'auth')
for line in sys.stdin:
    message = json.loads(line)
    if message.get('id') == 1:
        print(json.dumps({'id': 1, 'result': {}}), flush=True)
    elif message.get('id') == 2:
        if mode == 'auth':
            print(json.dumps({'id': 2, 'error': {'code': -32600, 'message': 'codex account authentication required'}}), flush=True)
        else:
            print(json.dumps({'id': 2, 'result': {'rateLimits': json.loads(mode)}}), flush=True)
        break
'''


def stamp(minutes_ago):
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).strftime('%Y-%m-%dT%H:%M:%S.000Z')


def claude_events(five_hour, weekly, minutes_ago, status='allowed'):
    return [{'receivedAt': stamp(minutes_ago), 'content': {'rawPayload': {'type': 'rate_limit_event', 'rate_limit_info': {
        'status': status, 'unifiedWindows': {'five_hour': {'utilization': five_hour / 100, 'resetsAt': 1790571600},
                                             'seven_day': {'utilization': weekly / 100, 'resetsAt': 1790960400}}}}}}]


def rollout(weekly, minutes_ago, reached=None):
    return json.dumps({'timestamp': stamp(minutes_ago), 'type': 'event_msg', 'payload': {'type': 'token_count', 'rate_limits': {
        'primary': {'used_percent': weekly, 'window_minutes': 10080, 'resets_at': 1791163718},
        'secondary': None, 'rate_limit_reached_type': reached}}}) + '\n'


class UsageTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.bin = self.root / 'bin'
        self.state = self.root / 'state'
        self.codex_home = self.root / 'codex'
        for directory in (self.bin, self.state, self.codex_home):
            directory.mkdir()
        for name, body in (('conductor', FAKE_CONDUCTOR), ('codex', FAKE_CODEX)):
            (self.bin / name).write_text(body)
            (self.bin / name).chmod(0o755)
        (self.state / 'sessions.json').write_text(json.dumps([
            {'id': 'current', 'model': 'opus-5-5-1m'}, {'id': 'worker', 'model': 'gpt-6-sol'}]))
        self.env = {**os.environ, 'PATH': f'{self.bin}{os.pathsep}{os.environ["PATH"]}', 'FAKE_STATE': str(self.state),
                    'CODEX_HOME': str(self.codex_home), 'CONDUCTOR_WORKSPACE_ID': 'workspace',
                    'CONDUCTOR_SESSION_ID': 'current', 'FAKE_CODEX': 'auth'}

    def claude(self, *args, session='current'):
        (self.state / f'{session}.json').write_text(json.dumps(claude_events(*args)))

    def codex_log(self, *args, **kwargs):
        path = self.codex_home / 'sessions' / '2026' / 'rollout-existing.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rollout(*args, **kwargs))

    def run_usage(self, *args):
        result = subprocess.run([sys.executable, str(SCRIPT), '--json', *args], env=self.env,
                                capture_output=True, text=True, timeout=60)
        self.assertIn(result.returncode, (0, 3), result.stderr)
        output = json.loads(result.stdout)
        output['returncode'] = result.returncode
        output['choice'] = {c['tier']: (c['agent'], c['model'], c['effort']) for c in output['choices']}
        output['fast'] = {c['tier']: c['fast'] for c in output['choices']}
        return output

    def calls(self):
        log = self.state / 'calls.log'
        return log.read_text() if log.exists() else ''

    def test_fresh_readings_choose_primaries_without_probes(self):
        self.claude(5, 1, 2)
        self.codex_log(10, 3)
        out = self.run_usage()
        self.assertEqual(out['choice'], {'frontier': ('claude', 'opus-5-5-1m', 'medium'),
                                         'fast': ('codex', 'gpt-6.1-sol', None),
                                         'trivial': ('codex', 'gpt-6-luna', None),
                                         'verify': ('codex', 'gpt-6.1-sol', 'low')})
        # Owner, 2026-10-03: all tiers use standard mode.
        self.assertEqual(out['fast'], {'frontier': False, 'fast': False, 'trivial': False, 'verify': False})
        self.assertEqual(out['accounts']['claude']['windows'][1], {'name': 'weekly', 'used_percent': 1.0,
                                                                   'resets_at': '2026-10-02T17:00:00Z'})
        self.assertNotIn('session create', self.calls())

    def test_claude_weekly_reserve_moves_frontier_to_astra_only(self):
        self.claude(20, 95, 1)
        self.codex_log(10, 1)
        out = self.run_usage()
        self.assertEqual(out['choice']['frontier'], ('codex', 'gpt-6-astra', None))
        self.assertEqual(out['choice']['fast'], ('codex', 'gpt-6.1-sol', None))
        self.assertIn('claude has no usage remaining', out['choices'][0]['reason'])
        # Both the fallback and routine work use standard mode.
        self.assertEqual((out['fast']['frontier'], out['fast']['fast']), (False, False))

    def test_just_below_reserve_keeps_primary(self):
        self.claude(89, 89, 1)
        self.codex_log(10, 1)
        self.assertEqual(self.run_usage()['choice']['frontier'], ('claude', 'opus-5-5-1m', 'medium'))

    def test_codex_limit_reached_uses_opus_low_for_fast_and_trivial(self):
        self.claude(5, 1, 1)
        self.codex_log(40, 1, reached='rate_limit_reached')
        out = self.run_usage()
        self.assertEqual(out['choice']['fast'], ('claude', 'opus-5-5-1m', 'low'))
        self.assertEqual(out['choice']['trivial'], ('claude', 'opus-5-5-1m', 'low'))
        self.assertEqual(out['choice']['frontier'], ('claude', 'opus-5-5-1m', 'medium'))

    def test_both_exhausted_holds_until_earliest_reset(self):
        self.claude(50, 97, 1, 'rejected')
        self.codex_log(99, 1)
        out = self.run_usage('--tier', 'frontier')
        self.assertEqual(out['returncode'], 3)
        self.assertEqual(out['choice']['frontier'], (None, None, None))
        self.assertEqual(out['choices'][0]['hold_until'], '2026-10-02T17:00:00Z')

    def test_stale_readings_are_refreshed_by_archived_probes(self):
        self.claude(5, 1, 45)
        self.codex_log(10, 45)
        (self.state / 'probe-claude.json').write_text(json.dumps(claude_events(30, 92, 0)))
        (self.state / 'probe-codex.json').write_text(rollout(20, 0))
        out = self.run_usage()
        calls = self.calls()
        self.assertIn('session create --agent claude --model haiku-4-5', calls)
        self.assertIn('session create --agent codex --model gpt-6-luna', calls)
        self.assertIn('session archive probe-claude-session', calls)
        self.assertIn('session archive probe-codex-session', calls)
        self.assertEqual(out['accounts']['claude']['windows'][1]['used_percent'], 92.0)
        self.assertEqual(out['choice']['frontier'], ('codex', 'gpt-6-astra', None))
        self.assertFalse(out['accounts']['codex']['stale'])

    def test_no_probe_reports_stale_and_unknown_without_launching(self):
        self.claude(5, 1, 45)
        out = self.run_usage('--no-probe')
        self.assertTrue(out['accounts']['claude']['stale'])
        self.assertNotIn('codex', out['accounts'])
        self.assertEqual(out['choice']['fast'], ('codex', 'gpt-6.1-sol', None))
        self.assertIn('codex usage unknown', out['choices'][1]['reason'])
        self.assertNotIn('session create', self.calls())

    def test_signed_in_codex_app_server_is_preferred_to_old_logs(self):
        self.claude(5, 1, 1)
        self.codex_log(10, 1)
        self.env['FAKE_CODEX'] = json.dumps({'primary': {'usedPercent': 96, 'windowDurationMins': 300, 'resetsAt': 1790571600},
                                             'secondary': {'usedPercent': 30, 'windowDurationMins': 10080, 'resetsAt': 1791163718},
                                             'rateLimitReachedType': None})
        out = self.run_usage('--no-probe')
        self.assertEqual(out['accounts']['codex']['source'], 'codex app-server')
        self.assertEqual([w['name'] for w in out['accounts']['codex']['windows']], ['five_hour', 'weekly'])
        self.assertEqual(out['choice']['fast'], ('claude', 'opus-5-5-1m', 'low'))

    def test_verify_uses_sol_low_standard_and_switches_family_for_codex_work(self):
        self.claude(5, 1, 1)
        self.codex_log(10, 1)
        out = self.run_usage('--tier', 'verify')
        self.assertEqual(out['choice']['verify'], ('codex', 'gpt-6.1-sol', 'low'))
        self.assertFalse(out['fast']['verify'])
        out = self.run_usage('--tier', 'verify', '--implementer', 'codex')
        self.assertEqual(out['choice']['verify'], ('claude', 'opus-5-5-1m', 'low'))
        self.assertFalse(out['fast']['verify'])
        self.assertIn('alternate: claude', out['choices'][0]['reason'])

    def test_verify_holds_rather_than_same_family_when_other_family_is_exhausted(self):
        self.claude(50, 95, 1)
        self.codex_log(10, 1)
        out = self.run_usage('--tier', 'verify', '--implementer', 'codex', '--map', str(self.state / 'no-map.json'))
        self.assertEqual(out['returncode'], 3)
        self.assertEqual(out['choice']['verify'], (None, None, None))
        self.assertIn('same family as the implementer', out['choices'][0]['reason'])

    def test_verify_falls_back_to_the_implementers_family_when_the_repository_allows_it(self):
        self.claude(5, 1, 1)
        self.codex_log(95, 1)
        allowed = self.state / 'allowed.json'
        allowed.write_text(json.dumps({'version': 1, 'allow_same_family': True}))
        out = self.run_usage('--tier', 'verify', '--implementer', 'claude', '--map', str(allowed))
        self.assertEqual(out['returncode'], 0)
        self.assertEqual(out['choice']['verify'], ('claude', 'opus-5-5-1m', 'low'))
        self.assertIn('same-family fallback', out['choices'][0]['reason'])
        # The other family still comes first while it has usage.
        self.codex_log(10, 1)
        out = self.run_usage('--tier', 'verify', '--implementer', 'claude', '--map', str(allowed))
        self.assertEqual(out['choice']['verify'], ('codex', 'gpt-6.1-sol', 'low'))

    def test_codex_exhaustion_moves_verification_to_opus_low_without_fast_mode(self):
        self.claude(5, 1, 1)
        self.codex_log(92, 1)
        out = self.run_usage('--tier', 'verify')
        self.assertEqual(out['choice']['verify'], ('claude', 'opus-5-5-1m', 'low'))
        self.assertFalse(out['fast']['verify'])

    def test_repository_model_rules_replace_and_forbid_models(self):
        # Owner, 2026-10-05 (Loopcraft): every Codex session uses gpt-6.1-sol; gpt-6-astra is forbidden.
        rules = self.state / 'coordination.json'
        rules.write_text(json.dumps({'models': {'codex': 'gpt-6.1-sol'}, 'forbidden_models': ['gpt-6-astra']}))
        self.claude(20, 95, 1)
        self.codex_log(10, 1)
        out = self.run_usage('--coordination', str(rules))
        self.assertEqual(out['choice']['frontier'], ('codex', 'gpt-6.1-sol', None))
        self.assertEqual(out['choice']['trivial'], ('codex', 'gpt-6.1-sol', None))
        rules.write_text(json.dumps({'forbidden_models': ['gpt-6-astra']}))
        out = self.run_usage('--coordination', str(rules))
        self.assertIsNone(out['choice']['frontier'][0])  # holds rather than launch a forbidden model
        self.assertIn('gpt-6-astra skipped: forbidden', out['choices'][0]['reason'])

    def test_policy_matches_model_reference(self):
        sys.path.insert(0, str(SCRIPT.parent))
        try:
            import usage
        finally:
            sys.path.pop(0)
        text = MODELS.read_text()
        for tier, options in usage.POLICY.items():
            row = next(line for line in text.splitlines() if line.lower().startswith(f'| {tier} '))
            found = re.findall(r'--agent (\w+) --model ([\w.-]+)(?: --effort (\w+))?( --fast-mode)?', row)
            self.assertEqual([(a, m, e or None, bool(f)) for a, m, e, f in found], options, tier)


if __name__ == '__main__':
    unittest.main()
