#!/usr/bin/env python3
"""Read Claude and Codex plan usage and choose each tier's model under the jfactory model policy."""
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Keep in step with references/models.md.
POLICY = {
    'frontier': [('claude', 'opus-5-5-1m', None), ('codex', 'gpt-6-astra', None)],
    'fast': [('codex', 'gpt-6-sol', None), ('claude', 'opus-5-5-1m', 'low')],
    'trivial': [('codex', 'gpt-6-luna', None), ('claude', 'opus-5-5-1m', 'low')],
}
PROBES = {'claude': ('haiku-4-5', None), 'codex': ('gpt-6-luna', 'low')}
PROBE_MESSAGE = 'Reply with the single word ok. Do not use any tools.'
CLAUDE_WINDOWS = {'five_hour': 'five_hour', 'seven_day': 'weekly'}
CODEX_WINDOWS = {300: 'five_hour', 10080: 'weekly'}
PAGE = 100
MAX_PAGES = 40


def now():
    return datetime.now(timezone.utc)


def iso(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        value = datetime.fromtimestamp(value, timezone.utc)
    return value.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def parse_time(text):
    return datetime.fromisoformat(text.replace('Z', '+00:00')) if text else None


def conductor(*args, timeout=30):
    result = subprocess.run(['conductor', '--json', *args], capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'conductor {" ".join(args[:2])} failed: {result.stderr.strip() or result.stdout.strip()}')
    return json.loads(result.stdout) if result.stdout.strip() else {}


def in_conductor():
    return bool(os.environ.get('CONDUCTOR_WORKSPACE_ID')) and subprocess.run(
        ['sh', '-c', 'command -v conductor'], capture_output=True).returncode == 0


def session_events(session_id):
    events = []
    for page in range(MAX_PAGES):
        data = conductor('session', 'message', session_id, '--limit', str(PAGE), '--offset', str(page * PAGE))
        events.extend(data.get('data') or [])
        if not data.get('hasMore'):
            break
    return events


def claude_reading_from_events(events, session_id):
    """Claude Code emits rate_limit_event when the reading changes; later responses confirm it."""
    reading = None
    for event in events:
        payload = (event.get('content') or {}).get('rawPayload') or {}
        if payload.get('type') == 'rate_limit_event':
            info = payload.get('rate_limit_info') or {}
            windows = [{'name': CLAUDE_WINDOWS[key], 'used_percent': round(value['utilization'] * 100, 1),
                        'resets_at': iso(value.get('resetsAt'))}
                       for key, value in (info.get('unifiedWindows') or {}).items()
                       if key in CLAUDE_WINDOWS and value.get('utilization') is not None]
            reading = {'account': 'claude', 'windows': windows, 'limited': info.get('status') == 'rejected',
                       'observed_at': event.get('receivedAt'), 'source': f'conductor session {session_id}'}
        elif reading and payload.get('type') == 'assistant':
            reading['observed_at'] = event.get('receivedAt') or reading['observed_at']
    return reading


def claude_sessions():
    ids = []
    current = os.environ.get('CONDUCTOR_SESSION_ID')
    if current:
        ids.append(current)
    try:
        data = conductor('workspace', 'session', '--limit', '100')
    except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return ids
    for session in (data.get('data') or [])[:10]:
        model = session.get('model') or ''
        if session.get('id') not in ids and not model.startswith('gpt') and not model.startswith('codex'):
            ids.append(session['id'])
    return ids


def read_claude(session_ids):
    best = None
    for session_id in session_ids:
        try:
            reading = claude_reading_from_events(session_events(session_id), session_id)
        except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError):
            continue
        if reading and (not best or parse_time(reading['observed_at']) > parse_time(best['observed_at'])):
            best = reading
    return best


def codex_reading(limits, observed_at, source):
    windows = []
    for key in ('primary', 'secondary'):
        window = limits.get(key)
        if not window:
            continue
        minutes = window.get('windowDurationMins', window.get('window_minutes'))
        used = window.get('usedPercent', window.get('used_percent'))
        if used is None:
            continue
        windows.append({'name': CODEX_WINDOWS.get(minutes, f'{minutes}_minutes'), 'used_percent': float(used),
                        'resets_at': iso(window.get('resetsAt', window.get('resets_at')))})
    reached = limits.get('rateLimitReachedType', limits.get('rate_limit_reached_type'))
    return {'account': 'codex', 'windows': windows, 'limited': bool(reached),
            'observed_at': observed_at, 'source': source}


def read_codex_app_server(timeout=20):
    requests = [
        {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'clientInfo': {'name': 'jfactory-usage', 'version': '1'}}},
        {'jsonrpc': '2.0', 'method': 'initialized'},
        {'jsonrpc': '2.0', 'id': 2, 'method': 'account/rateLimits/read'},
    ]
    try:
        process = subprocess.Popen(['codex', 'app-server'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, text=True)
    except OSError:
        return None
    try:
        process.stdin.write(''.join(json.dumps(r) + '\n' for r in requests))
        process.stdin.flush()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = process.stdout.readline()
            if not line:
                return None
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if message.get('id') == 2:
                limits = (message.get('result') or {}).get('rateLimits')
                return codex_reading(limits, iso(now()), 'codex app-server') if limits else None
        return None
    finally:
        process.kill()
        process.wait()


def read_codex_rollouts(codex_home):
    sessions = Path(codex_home) / 'sessions'
    if not sessions.is_dir():
        return None
    files = sorted(sessions.rglob('rollout-*.jsonl'), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in files[:20]:
        found = None
        for line in path.read_text(errors='replace').splitlines():
            if '"rate_limits"' not in line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            limits = (record.get('payload') or {}).get('rate_limits')
            if limits:
                found = codex_reading(limits, record.get('timestamp'), f'codex session log {path.name}')
        if found:
            return found
    return None


def read_codex(codex_home):
    return read_codex_app_server() or read_codex_rollouts(codex_home)


def age_minutes(reading):
    observed = parse_time(reading.get('observed_at'))
    return (now() - observed).total_seconds() / 60 if observed else float('inf')


def probe(agent, codex_home):
    model, effort = PROBES[agent]
    args = ['session', 'create', '--agent', agent, '--model', model, '--name', 'jfactory usage probe',
            '--message', PROBE_MESSAGE]
    if effort:
        args += ['--effort', effort]
    session_id = conductor(*args)['id']
    try:
        deadline = time.monotonic() + 180
        time.sleep(2)
        while time.monotonic() < deadline:
            if conductor('session', 'status', session_id).get('status') == 'idle':
                break
            time.sleep(3)
        if agent == 'claude':
            return claude_reading_from_events(session_events(session_id), session_id)
        return read_codex_rollouts(codex_home)
    finally:
        try:
            conductor('session', 'archive', session_id)
        except (RuntimeError, subprocess.TimeoutExpired, json.JSONDecodeError):
            print(f'warning: could not archive probe session {session_id}', file=sys.stderr)


def exhausted(reading, reserve):
    if not reading:
        return False
    return reading['limited'] or any(w['used_percent'] >= reserve for w in reading['windows'])


def earliest_reset(reading, reserve):
    times = [w['resets_at'] for w in reading['windows'] if w['used_percent'] >= reserve and w['resets_at']]
    return min(times) if times else None


def choose(tier, readings, reserve):
    notes = []
    for agent, model, effort in POLICY[tier]:
        reading = readings.get(agent)
        if not reading:
            return {'tier': tier, 'agent': agent, 'model': model, 'effort': effort,
                    'reason': '; '.join(notes + [f'{agent} usage unknown; start on this model and switch if it stops at a limit'])}
        if not exhausted(reading, reserve):
            reason = 'primary' if not notes else 'fallback'
            return {'tier': tier, 'agent': agent, 'model': model, 'effort': effort,
                    'reason': '; '.join(notes + [f'{reason}: {agent} {summary(reading)}'])}
        notes.append(f'{agent} has no usage remaining ({summary(reading)})')
    resets = [earliest_reset(readings[a], reserve) for a, _, _ in POLICY[tier] if readings.get(a)]
    resets = [r for r in resets if r]
    return {'tier': tier, 'agent': None, 'model': None, 'effort': None,
            'hold_until': min(resets) if resets else None, 'reason': '; '.join(notes)}


def summary(reading):
    parts = [f"{w['name']} {w['used_percent']:g}%" for w in reading['windows']]
    if reading['limited']:
        parts.append('limit reached')
    return ', '.join(parts) or 'no windows reported'


def collect(args):
    readings = {}
    probing = not args.no_probe and in_conductor()
    claude = read_claude(claude_sessions()) if in_conductor() else None
    if probing and (not claude or age_minutes(claude) > args.max_age):
        claude = probe('claude', args.codex_home) or claude
    codex = read_codex(args.codex_home)
    if probing and (not codex or age_minutes(codex) > args.max_age):
        codex = probe('codex', args.codex_home) or codex
    for reading in (claude, codex):
        if reading:
            reading['age_minutes'] = round(age_minutes(reading), 1)
            reading['stale'] = reading['age_minutes'] > args.max_age
            readings[reading['account']] = reading
    return readings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tier', choices=sorted(POLICY), action='append',
                        help='tier to choose a model for; repeat for several (default: all)')
    parser.add_argument('--reserve', type=float, default=90, help='used percent that counts as no usage remaining')
    parser.add_argument('--max-age', type=float, default=20, help='minutes before a reading is refreshed by a probe')
    parser.add_argument('--no-probe', action='store_true', help='never launch a probe session')
    parser.add_argument('--codex-home', default=os.environ.get('CODEX_HOME') or str(Path.home() / '.codex'))
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    readings = collect(args)
    choices = [choose(tier, readings, args.reserve) for tier in (args.tier or ['frontier', 'fast', 'trivial'])]
    if args.json:
        print(json.dumps({'checked_at': iso(now()), 'reserve_percent': args.reserve, 'accounts': readings,
                          'choices': choices}, indent=2))
    else:
        for account in ('claude', 'codex'):
            reading = readings.get(account)
            if not reading:
                print(f'{account}: usage unknown')
                continue
            windows = ', '.join(f"{w['name']} {w['used_percent']:g}% (resets {w['resets_at']})" for w in reading['windows'])
            stale = ' STALE' if reading['stale'] else ''
            limited = ' LIMIT REACHED' if reading['limited'] else ''
            print(f"{account}: {windows or 'no windows reported'}{limited}; observed {reading['age_minutes']:g} min ago{stale} via {reading['source']}")
        for choice in choices:
            if choice['model']:
                effort = f" --effort {choice['effort']}" if choice['effort'] else ''
                print(f"{choice['tier']}: --agent {choice['agent']} --model {choice['model']}{effort}  [{choice['reason']}]")
            else:
                print(f"{choice['tier']}: HOLD until {choice['hold_until'] or 'a reset'}  [{choice['reason']}]")
    return 3 if any(not c['model'] for c in choices) else 0


if __name__ == '__main__':
    sys.exit(main())
