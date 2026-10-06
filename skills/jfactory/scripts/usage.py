#!/usr/bin/env python3
"""Read Claude and Codex plan usage and choose each tier's model under the jfactory model policy."""
import argparse
import fnmatch
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Keep in step with references/models.md.
# Each option is (agent, model, effort, fast mode).
POLICY = {
    # Owner, 2026-10-03: all primary and fallback defaults use standard mode to avoid fast-mode credits.
    'frontier': [('claude', 'opus-5-5-1m', 'medium', False), ('codex', 'gpt-6-astra', None, False)],
    'fast': [('codex', 'gpt-6.1-sol', None, False), ('claude', 'opus-5-5-1m', 'low', False)],
    'trivial': [('codex', 'gpt-6-luna', None, False), ('claude', 'opus-5-5-1m', 'low', False)],
    # Verification keeps low effort and the same evidence requirements.
    'verify': [('codex', 'gpt-6.1-sol', 'low', False), ('claude', 'opus-5-5-1m', 'low', False)],
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


def probe(agent, codex_home, rules=({}, set())):
    model, effort = probe_model(agent, rules)
    if not model:
        return None
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


DEFAULT_COORDINATION = '.jfactory/coordination.json'


def model_rules(path=DEFAULT_COORDINATION, required=False):
    """The repository's `models` (agent -> model) and `forbidden_models` from .jfactory/coordination.json.
    A missing default file means no rules. A settings file that exists but cannot be read, or a path the caller named
    that is missing, stops the script: silently dropping the rules could launch a forbidden model."""
    path = Path(path)
    if not path.exists():
        if required:
            raise SystemExit(f'usage.py: {path} does not exist')
        return {}, set()
    try:
        return parse_model_rules(json.loads(path.read_text()))
    except (OSError, ValueError) as error:
        raise SystemExit(f'usage.py: cannot read the model rules in {path}: {error}')


def parse_model_rules(data):
    """Validate the settings' model rules; raise ValueError on any wrong type, so no reader silently drops a rule.
    `models` is an object mapping an agent to a non-empty model id; `forbidden_models` is a list of model ids."""
    if not isinstance(data, dict):
        raise ValueError('the settings must be a JSON object')
    models = data.get('models', {})
    forbidden = data.get('forbidden_models', [])
    if not isinstance(models, dict) or not all(isinstance(k, str) and k and isinstance(v, str) and v
                                               for k, v in models.items()):
        raise ValueError('"models" must map each agent to a model id, for example {"codex": "gpt-6.1-sol"}')
    if not isinstance(forbidden, list) or not all(isinstance(m, str) and m for m in forbidden):
        raise ValueError('"forbidden_models" must be a list of model ids, for example ["gpt-6-astra"]')
    if any(model in forbidden for model in models.values()):
        raise ValueError('"models" names a model that "forbidden_models" forbids')
    return dict(models), set(forbidden)


def parse_ui_rules(data):
    """The settings' `ui` rules, or None. UI work is work whose result people see on a screen; some models do it badly.
    `allowed_models` maps each agent to the only models UI work may use, best first; an agent it leaves out cannot do
    UI work. `paths` lists globs (`*` also matches `/`) whose changes make a launch UI work. For UI work these rules
    replace `models` and `forbidden_models`. Raise ValueError on any wrong type, so no reader silently drops a rule."""
    ui = data.get('ui') if isinstance(data, dict) else None
    if ui is None:
        return None
    allowed = ui.get('allowed_models') if isinstance(ui, dict) else None
    if not isinstance(allowed, dict) or not allowed or not all(
            isinstance(k, str) and k and isinstance(v, list) and v and all(isinstance(m, str) and m for m in v)
            for k, v in allowed.items()):
        raise ValueError('"ui.allowed_models" must map each agent to a non-empty list of model ids, '
                         'for example {"claude": ["opus-5-5-1m"]}')
    paths = ui.get('paths', [])
    if not isinstance(paths, list) or not all(isinstance(p, str) and p for p in paths):
        raise ValueError('"ui.paths" must be a list of path globs, for example ["src/components/*"]')
    return {'allowed': {k: list(v) for k, v in allowed.items()}, 'paths': list(paths)}


def ui_rules(path=DEFAULT_COORDINATION, required=False):
    """The repository's UI rules from .jfactory/coordination.json, or None. Fails like model_rules."""
    path = Path(path)
    if not path.exists():
        if required:
            raise SystemExit(f'usage.py: {path} does not exist')
        return None
    try:
        return parse_ui_rules(json.loads(path.read_text()))
    except (OSError, ValueError) as error:
        raise SystemExit(f'usage.py: cannot read the UI rules in {path}: {error}')


def ui_paths(paths, ui):
    """The changed paths that make work UI work under the rules."""
    return [p for p in paths if any(fnmatch.fnmatchcase(p, pattern) for pattern in ui['paths'])] if ui else []


def ui_model(agent, model, ui):
    """The model this agent uses for UI work: the given one when allowed, else the agent's first allowed model,
    or None when the agent cannot do UI work."""
    allowed = ui['allowed'].get(agent) or []
    return model if model in allowed else (allowed[0] if allowed else None)


def probe_model(agent, rules):
    """The probe's model under the repository's rules, or None when no allowed model is left."""
    models, forbidden = rules
    model, effort = PROBES[agent]
    model = models.get(agent, model)
    return (None, None) if model in forbidden else (model, effort)


def choose(tier, readings, reserve, implementer=None, allow_same_family=False, rules=None, ui=None):
    notes = []
    models, forbidden = rules or ({}, set())
    if ui:
        # UI work: the repository's UI allowlist replaces `models` and `forbidden_models`.
        options = [(a, ui_model(a, m, ui), e, f) for a, m, e, f in POLICY[tier]]
        notes += [f'{a} skipped: no model allowed for UI work' for a, m, *_ in options if not m]
        options = [o for o in options if o[1]]
    else:
        options = [(a, models.get(a, m), e, f) for a, m, e, f in POLICY[tier]]
        for a, m, *_ in list(options):
            if m in forbidden:
                notes.append(f'{a}/{m} skipped: forbidden by the repository')
        options = [o for o in options if o[1] not in forbidden]
    if tier == 'verify' and implementer:
        other = [option for option in options if option[0] != implementer]
        if allow_same_family:
            # The repository accepts same-family verdicts, so a verifier from the implementer's family is the fallback
            # when the other family has no usage, instead of holding the review.
            options = other + [option for option in options if option[0] == implementer]
        else:
            notes = [f'{a} skipped: same family as the implementer' for a, *_ in options if a == implementer]
            options = other
    for agent, model, effort, fast in options:
        choice = {'tier': tier, 'agent': agent, 'model': model, 'effort': effort, 'fast': fast}
        reading = readings.get(agent)
        if not reading:
            return {**choice, 'reason': '; '.join(notes + [f'{agent} usage unknown; start on this model and switch if it stops at a limit'])}
        if not exhausted(reading, reserve):
            if agent == POLICY[tier][0][0]:
                reason = 'primary'
            elif tier == 'verify' and implementer == agent:
                reason = 'same-family fallback'  # allowed by the repository's allow_same_family
            elif tier == 'verify' and implementer == POLICY[tier][0][0]:
                reason = 'alternate'  # the family switch for a verifier, not a usage fallback
            else:
                reason = 'fallback'
            return {**choice, 'reason': '; '.join(notes + [f'{reason}: {agent} {summary(reading)}'])}
        notes.append(f'{agent} has no usage remaining ({summary(reading)})')
    resets = [earliest_reset(readings[a], reserve) for a, *_ in options if readings.get(a)]
    resets = [r for r in resets if r]
    return {'tier': tier, 'agent': None, 'model': None, 'effort': None, 'fast': False,
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
        claude = probe('claude', args.codex_home, args.rules) or claude
    codex = read_codex(args.codex_home)
    if probing and (not codex or age_minutes(codex) > args.max_age):
        codex = probe('codex', args.codex_home, args.rules) or codex
    for reading in (claude, codex):
        if reading:
            reading['age_minutes'] = round(age_minutes(reading), 1)
            reading['stale'] = reading['age_minutes'] > args.max_age
            readings[reading['account']] = reading
    return readings


def allow_same_family(path):
    try:
        return json.loads(Path(path).read_text()).get('allow_same_family') is True
    except (OSError, ValueError, AttributeError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tier', choices=sorted(POLICY), action='append',
                        help='tier to choose a model for; repeat for several (default: all)')
    parser.add_argument('--implementer', choices=['claude', 'codex'],
                        help='agent that implemented the work under verification; the verify tier skips its family')
    parser.add_argument('--reserve', type=float, default=90, help='used percent that counts as no usage remaining')
    parser.add_argument('--max-age', type=float, default=20, help='minutes before a reading is refreshed by a probe')
    parser.add_argument('--no-probe', action='store_true', help='never launch a probe session')
    parser.add_argument('--codex-home', default=os.environ.get('CODEX_HOME') or str(Path.home() / '.codex'))
    parser.add_argument('--map', default='.jfactory/verification.json',
                        help='verification map whose "allow_same_family" lets a verifier fall back to the implementer\'s family')
    parser.add_argument('--coordination',
                        help='repository settings whose "models" and "forbidden_models" override the policy')
    parser.add_argument('--ui', action='store_true',
                        help='choose for UI work under the "ui" rules in the repository settings')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    # Rules come first: probes launch sessions, so they obey the rules too.
    args.rules = model_rules(args.coordination or DEFAULT_COORDINATION, required=bool(args.coordination))
    ui = ui_rules(args.coordination or DEFAULT_COORDINATION, required=bool(args.coordination)) if args.ui else None
    if args.ui and not ui:
        raise SystemExit('usage.py: --ui needs a "ui" section with "allowed_models" in the repository settings')
    readings = collect(args)
    same = allow_same_family(args.map)
    choices = [choose(tier, readings, args.reserve, args.implementer, same, args.rules, ui)
               for tier in (args.tier or list(POLICY))]
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
                fast = ' --fast-mode' if choice['fast'] else ''
                print(f"{choice['tier']}: --agent {choice['agent']} --model {choice['model']}{effort}{fast}  [{choice['reason']}]")
            else:
                print(f"{choice['tier']}: HOLD until {choice['hold_until'] or 'a reset'}  [{choice['reason']}]")
    return 3 if any(not c['model'] for c in choices) else 0


if __name__ == '__main__':
    sys.exit(main())
