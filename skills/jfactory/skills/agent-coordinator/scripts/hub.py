#!/usr/bin/env python3
"""The agent hub: one pinned GitHub issue that names the agent the owner talks to, and holds its ledger.

The hub is the highest-level agent. Coordinators send it QUESTION, BLOCKER, RISK, MILESTONE and DIGEST messages;
workers never do. It asks the owner only for decisions, blockers and risks it cannot clear, and keeps its state here,
not in its chat, so it can hand over to a fresh session without losing open questions.

    hub.py claim [--session ID] [--agent claude|codex] [--notify]   become the hub (a second claim takes over)
    hub.py check [--session ID]                                      exit 3 when this session is no longer the hub
    hub.py show [--json]                                             the hub, how to reach it, and the open ledger
    hub.py coordinators                                              coordinator sessions of open jfactory programs
    hub.py broadcast --message TEXT                                  message every coordinator (or comment its program)
    hub.py route --from SESSION                                      who sent this: coordinator, worker or unknown
    hub.py ledger add --kind question|blocker|risk|decision|hold --text T [--owner S] [--from S] [--eta E]
    hub.py ledger resolve ID --answer TEXT [--relay]                 record the answer; --relay sends it to the owner
    hub.py ledger list [--all]
    hub.py status                                                    a status table from programs and the ledger
    hub.py handoff [--to SESSION | --create --workspace W] [--reason R]

Standard library only, so the global copy works in any repository. It needs `gh` (authenticated); `conductor` is
optional: without it, messages become comments on the program issues and the hub issue.
"""
import argparse
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

HUB_LABEL = 'jfactory-hub'
HUB_TITLE = 'Agent hub'
PROGRAM_LABEL = 'jfactory-program'
STATE_RE = re.compile(r'<!-- jfactory-hub\n(.*?)\n-->', re.S)
PROGRAM_RE = re.compile(r'<!-- jfactory-program\n(.*?)\n-->', re.S)
KINDS = ('question', 'blocker', 'risk', 'decision', 'hold')
TAGS = ('QUESTION', 'BLOCKER', 'RISK', 'MILESTONE', 'DIGEST')
ROUTING = ('Only coordinators message the hub, tagged QUESTION (needs the owner), BLOCKER, RISK, MILESTONE (merged or '
           'live) or DIGEST (routine progress, at most one every 30 minutes). Workers report to their coordinator, '
           'never to the hub.')


class Refused(Exception):
    pass


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def run(tool, *args, check=True):
    exe = os.environ.get(f'JFACTORY_{tool.upper()}', tool)
    try:
        proc = subprocess.run([exe, *args], capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        if check:
            raise Refused(f'{tool} is not installed or not on PATH')
        return None
    except subprocess.TimeoutExpired:
        raise Refused(f'{tool} {" ".join(args[:3])} timed out')
    if proc.returncode:
        if check:
            raise Refused(f'{tool} {" ".join(args[:3])} failed: {proc.stderr.strip() or proc.stdout.strip()}')
        return None
    return proc.stdout


def gh(repo, *args):
    return run('gh', *args, '--repo', repo)


def text_file(text):
    handle = tempfile.NamedTemporaryFile('w', suffix='.md', delete=False)
    handle.write(text)
    handle.close()
    return handle.name


def has_conductor():
    return run('conductor', '--help', check=False) is not None


def message(session, text):
    """Send a Conductor message; False when Conductor is not available."""
    if not session or not has_conductor():
        return False
    return run('conductor', 'message', 'create', '--session', session, '--message-file', text_file(text),
               check=False) is not None


def current_repo():
    return run('gh', 'repo', 'view', '--json', 'nameWithOwner', '--jq', '.nameWithOwner').strip()


# The hub issue

def find_hub(repo):
    found = json.loads(gh(repo, 'issue', 'list', '--label', HUB_LABEL, '--state', 'open', '--limit', '5',
                          '--json', 'number,title,url,state') or '[]')
    return found[0] if found else None


def load(repo):
    issue = find_hub(repo)
    if not issue:
        return None, {'version': 1, 'hub': None, 'history': [], 'ledger': [], 'next_id': 1}
    body = json.loads(gh(repo, 'issue', 'view', str(issue['number']), '--json', 'body,url'))
    match = STATE_RE.search(body.get('body') or '')
    state = json.loads(match.group(1)) if match else {'version': 1, 'hub': None, 'history': [], 'ledger': [],
                                                      'next_id': 1}
    state['_number'], state['_url'] = issue['number'], body.get('url') or issue.get('url')
    return issue['number'], state


def render(state):
    hub = state.get('hub') or {}
    open_items = [item for item in state['ledger'] if item['status'] == 'open']
    lines = [f'# {HUB_TITLE}', '',
             'The agent the owner talks to. jfactory\'s `agent-coordinator` skill keeps this issue; do not edit it '
             'by hand.', '',
             f"**Hub session:** `{hub.get('session') or 'none'}` ({hub.get('agent') or '?'} on "
             f"{hub.get('host') or '?'}), since {hub.get('since') or '?'}.", '', ROUTING, '',
             'Message the hub with: `conductor message create --session <hub session> --message "<TAG> <unit>: '
             '<text>, options, your default"`. Without Conductor, comment on this issue.', '',
             f'## Open items ({len(open_items)})', '']
    if open_items:
        lines += ['| ID | Kind | From | Owner of the action | Item | ETA |', '| --- | --- | --- | --- | --- | --- |']
        lines += [f"| {i['id']} | {i['kind']} | {i.get('from') or ''} | {i.get('owner') or ''} | "
                  f"{i['text'].replace('|', '/')} | {i.get('eta') or ''} |" for i in open_items]
    else:
        lines.append('None.')
    data = {k: v for k, v in state.items() if not k.startswith('_')}
    return '\n'.join(lines) + f'\n\n<!-- jfactory-hub\n{json.dumps(data, indent=1)}\n-->\n'


def save(repo, number, state):
    if number is None:
        try:
            gh(repo, 'label', 'create', HUB_LABEL, '--color', '5319E7', '--description', 'jfactory agent hub')
        except Refused:
            pass  # the label exists
        url = gh(repo, 'issue', 'create', '--title', HUB_TITLE, '--label', HUB_LABEL,
                 '--body-file', text_file(render(state))).strip()
        number = int(url.rstrip('/').rsplit('/', 1)[-1])
        run('gh', 'issue', 'pin', str(number), '--repo', repo, check=False)
        state['_url'] = url
    else:
        gh(repo, 'issue', 'edit', str(number), '--body-file', text_file(render(state)))
    state['_number'] = number
    return number


# Coordinators and workers, read from jfactory program issues

def programs(repo):
    found = json.loads(gh(repo, 'issue', 'list', '--label', PROGRAM_LABEL, '--state', 'open', '--limit', '50',
                          '--json', 'number,title,url') or '[]')
    result = []
    for issue in found:
        body = json.loads(gh(repo, 'issue', 'view', str(issue['number']), '--json', 'body')).get('body') or ''
        match = PROGRAM_RE.search(body)
        if match:
            result.append({**issue, 'state': json.loads(match.group(1))})
    return result


def coordinators(repo):
    return [{'program': p['number'], 'title': p['title'], 'session': p['state'].get('coordinator_session')}
            for p in programs(repo)]


def route(repo, sender, state):
    hub = (state.get('hub') or {}).get('session')
    if sender and sender == hub:
        return 'hub', None
    for p in programs(repo):
        if sender and sender == p['state'].get('coordinator_session'):
            return 'coordinator', p
        for name, unit in p['state'].get('units', {}).items():
            if sender and sender == unit.get('session'):
                return 'worker', {**p, 'unit': name}
    return 'unknown', None


# Commands

def cmd_claim(args):
    number, state = load(args.repo)
    session = args.session or os.environ.get('CONDUCTOR_SESSION_ID')
    if not session:
        raise Refused('No session id: pass --session, or run inside Conductor (CONDUCTOR_SESSION_ID)')
    previous = state.get('hub')
    if previous and previous.get('session') == session:
        print(f"Already the hub: {session}")
        return
    state['hub'] = {'session': session, 'agent': args.agent, 'host': socket.gethostname(), 'since': now()}
    if previous:
        state['history'].append({**previous, 'until': state['hub']['since']})
    save(args.repo, number, state)
    print(f"Hub: {session} ({state['_url']})")
    if previous:
        print(f"Took over from {previous['session']}")
    if args.notify:
        if previous and not message(previous['session'], f"HUB HANDOVER: {session} is now the agent hub "
                                    f"({state['_url']}). Stop relaying; send anything open to the new hub."):
            gh(args.repo, 'issue', 'comment', str(state['_number']), '--body-file',
               text_file(f"Hub moved from `{previous['session']}` to `{session}`."))
        broadcast(args.repo, f"AGENT HUB: {session} is now the hub ({state['_url']}). {ROUTING} "
                             'Tell every worker you run, including relaunches, to report only to you.')


def cmd_check(args):
    _, state = load(args.repo)
    session = args.session or os.environ.get('CONDUCTOR_SESSION_ID')
    hub = (state.get('hub') or {}).get('session')
    if hub != session:
        print(f'You are no longer the hub; {hub or "nobody"} is ({state.get("_url") or "no hub issue"}). '
              'Stop relaying and send anything open to the hub.')
        sys.exit(3)
    print(f'You are the hub ({state["_url"]}).')


def cmd_show(args):
    _, state = load(args.repo)
    if args.json:
        print(json.dumps({k: v for k, v in state.items() if not k.startswith('_')}, indent=1))
    else:
        print(render(state).split('\n<!-- jfactory-hub')[0])


def cmd_coordinators(args):
    for c in coordinators(args.repo):
        print(f"#{c['program']} {c['title']}: {c['session'] or 'no session recorded (comment on the program issue)'}")


def broadcast(repo, text):
    for c in coordinators(repo):
        if not message(c['session'], text):
            gh(repo, 'issue', 'comment', str(c['program']), '--body-file', text_file(text))
        print(f"Told #{c['program']} ({c['session'] or 'issue comment'})")


def cmd_broadcast(args):
    broadcast(args.repo, args.message)


def cmd_route(args):
    _, state = load(args.repo)
    kind, program = route(args.repo, args.sender, state)
    if kind == 'worker':
        coordinator = program['state'].get('coordinator_session')
        text = (f"Workers do not message the hub. Report to your coordinator for program #{program['number']} "
                f"({coordinator or 'comment on the program issue'}) with coord.py report.")
        print(f"worker {program['unit']} of #{program['number']}: {text}")
        if args.reply:
            message(args.sender, text)
    elif kind == 'coordinator':
        print(f"coordinator of #{program['number']} {program['title']}")
    else:
        print(kind)


def cmd_ledger(args):
    number, state = load(args.repo)
    if args.action == 'list':
        items = state['ledger'] if args.all else [i for i in state['ledger'] if i['status'] == 'open']
        for i in items:
            print(f"{i['id']} {i['status']} {i['kind']} from={i.get('from') or '-'} owner={i.get('owner') or '-'}: "
                  f"{i['text']}" + (f" -> {i['answer']}" if i.get('answer') else ''))
        return
    if number is None:
        raise Refused('No hub yet: run hub.py claim first')
    if args.action == 'add':
        if args.kind == 'hold' and not args.owner:
            raise Refused('A hold needs --owner: the session that owns the action, so the hold reaches it')
        item = {'id': f"H{state['next_id']}", 'kind': args.kind, 'text': args.text, 'from': args.sender,
                'owner': args.owner, 'eta': args.eta, 'status': 'open', 'opened': now()}
        state['next_id'] += 1
        state['ledger'].append(item)
        save(args.repo, number, state)
        print(item['id'])
        if args.kind == 'hold':
            # A hold the hub promises the owner must reach the agent that owns the action (2026-10-04: a PR merged
            # while the hub said it was held).
            if not message(args.owner, f"HOLD from the agent hub ({item['id']}): {args.text}. Do not proceed until "
                                       'the hub lifts it.'):
                print(f'Could not message {args.owner}; tell it yourself before promising the hold.')
            else:
                print(f'Hold sent to {args.owner}')
    else:  # resolve
        item = next((i for i in state['ledger'] if i['id'] == args.id), None)
        if not item:
            raise Refused(f'No ledger item {args.id}')
        item.update(status='resolved', answer=args.answer, resolved=now())
        save(args.repo, number, state)
        target = item.get('owner') or item.get('from')
        if args.relay:
            sent = message(target, f"ANSWER {item['id']} from the agent hub: {args.answer} (your {item['kind']}: "
                                   f"{item['text']})")
            print(f"Relayed to {target}" if sent else f'Could not message {target}; relay it yourself')
        print(f"{item['id']} resolved")


def cmd_status(args):
    _, state = load(args.repo)
    rows = ['| Workstream | Status | Summary | ETA |', '| --- | --- | --- | --- |']
    for p in programs(args.repo):
        units = p['state'].get('units', {})
        counts = {}
        for unit in units.values():
            counts[unit['state']] = counts.get(unit['state'], 0) + 1
        summary = ', '.join(f'{n} {s}' for s, n in sorted(counts.items())) or 'no units'
        prs = [f"#{u['pr']}" for u in units.values() if u.get('pr') and u['state'] in ('running', 'in-review')]
        status = 'done' if units and all(u['state'] in ('merged', 'done', 'abandoned') for u in units.values()) \
            else 'blocked' if counts.get('blocked') else 'active'
        rows.append(f"| #{p['number']} {p['title']} | {status} | {summary}{'; open PRs ' + ' '.join(prs) if prs else ''}"
                    f" | {p['state'].get('eta') or ''} |")
    open_items = [i for i in state['ledger'] if i['status'] == 'open']
    print('\n'.join(rows))
    print(f'\nOpen items: {len(open_items)}')
    for i in open_items:
        print(f"- {i['id']} {i['kind'].upper()}: {i['text']} (owner {i.get('owner') or '-'}, ETA {i.get('eta') or '-'})")


def cmd_handoff(args):
    number, state = load(args.repo)
    if number is None:
        raise Refused('No hub yet: run hub.py claim first')
    old = (state.get('hub') or {}).get('session')
    target = args.to
    if args.create:
        if not has_conductor():
            raise Refused('--create needs the conductor CLI; start a session yourself and pass --to')
        prompt = (f"You are taking over as the agent hub for {args.repo}. Run the agent-coordinator skill now. "
                  f"Read the ledger first (hub.py show), then claim with --notify. Previous hub: {old}. "
                  f"Reason: {args.reason or 'context handoff'}.")
        created = json.loads(run('conductor', '--json', 'session', 'create', '--workspace', args.workspace,
                                 '--agent', args.agent, '--message-file', text_file(prompt)) or '{}')
        target = created.get('id') or created.get('sessionId') or (created.get('session') or {}).get('id')
        if not target:
            raise Refused('conductor did not return the new session id')
    if not target:
        raise Refused('Pass --to <session>, or --create --workspace <id>')
    state['hub'] = {'session': target, 'agent': args.agent, 'host': socket.gethostname(), 'since': now()}
    if old:
        state['history'].append({'session': old, 'until': state['hub']['since'], 'reason': args.reason or 'handoff'})
    save(args.repo, number, state)
    open_items = [i['id'] for i in state['ledger'] if i['status'] == 'open']
    if not args.create:
        message(target, f"You are now the agent hub for {args.repo} ({state['_url']}). Run the agent-coordinator "
                        f"skill, read the ledger with hub.py show, and continue. Open items: {', '.join(open_items) or 'none'}.")
    broadcast(args.repo, f"AGENT HUB: handed over from {old} to {target} ({state['_url']}). {ROUTING}")
    print(f'Hub: {target}. Open items carried over: {", ".join(open_items) or "none"}. Tell the owner the new session.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--repo', help='OWNER/NAME; defaults to the current repository')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('claim')
    p.add_argument('--session')
    p.add_argument('--agent', default=os.environ.get('JFACTORY_AGENT', 'claude'))
    p.add_argument('--notify', action='store_true', help='tell the previous hub and every coordinator')
    p.set_defaults(func=cmd_claim)
    p = sub.add_parser('check')
    p.add_argument('--session')
    p.set_defaults(func=cmd_check)
    p = sub.add_parser('show')
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=cmd_show)
    sub.add_parser('coordinators').set_defaults(func=cmd_coordinators)
    p = sub.add_parser('broadcast')
    p.add_argument('--message', required=True)
    p.set_defaults(func=cmd_broadcast)
    p = sub.add_parser('route')
    p.add_argument('--from', dest='sender', required=True)
    p.add_argument('--reply', action='store_true', help='tell a worker to go through its coordinator')
    p.set_defaults(func=cmd_route)
    p = sub.add_parser('ledger')
    lsub = p.add_subparsers(dest='action', required=True)
    a = lsub.add_parser('add')
    a.add_argument('--kind', choices=KINDS, required=True)
    a.add_argument('--text', required=True)
    a.add_argument('--owner', help='session that owns the action (required for a hold)')
    a.add_argument('--from', dest='sender')
    a.add_argument('--eta')
    r = lsub.add_parser('resolve')
    r.add_argument('id')
    r.add_argument('--answer', required=True)
    r.add_argument('--relay', action='store_true')
    lst = lsub.add_parser('list')
    lst.add_argument('--all', action='store_true')
    p.set_defaults(func=cmd_ledger)
    sub.add_parser('status').set_defaults(func=cmd_status)
    p = sub.add_parser('handoff')
    p.add_argument('--to')
    p.add_argument('--create', action='store_true')
    p.add_argument('--workspace')
    p.add_argument('--agent', default=os.environ.get('JFACTORY_AGENT', 'claude'))
    p.add_argument('--reason')
    p.set_defaults(func=cmd_handoff)
    args = parser.parse_args(argv)
    try:
        args.repo = args.repo or current_repo()
        args.func(args)
    except Refused as error:
        print(f'REFUSED: {error}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
