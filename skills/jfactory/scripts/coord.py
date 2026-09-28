#!/usr/bin/env python3
"""Coordinate several Conductor workspaces through one GitHub program issue.

The issue body is the coordinator's state and has one writer. Workers report by
posting structured comments, which the coordinator folds in with `sync`.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PROGRAM_LABEL = 'jfactory-program'
HOLD_LABEL = 'jfactory-hold'
STATE_RE = re.compile(r'<!-- jfactory-program\n(.*?)\n-->', re.S)
REPORT_RE = re.compile(r'<!-- jfactory-report (\{.*?\}) -->', re.S)
STATES = ['planned', 'running', 'blocked', 'in-review', 'verified', 'merged', 'failed', 'abandoned']
WORKER_STATES = {'running', 'blocked', 'in-review', 'failed'}
ACTIVE = {'running'}
TERMINAL = {'merged', 'abandoned'}
VERDICTS = {'verified', 'partially-verified', 'blocked', 'failed'}
MAX_ATTEMPTS = 3
BRIEF_FIELDS = ['OBJECTIVE', 'DECISIONS', 'SCOPE', 'CONTEXT', 'ACCEPTANCE', 'VERIFY', 'SHARED',
                'LIMITS', 'FORBIDDEN', 'DELIVERY', 'REPORT']

# Roles map to Conductor agents. Review deliberately uses another model family.
DEFAULT_POLICY = {
    'limit': 3,
    'roles': {
        'implement': {'agent': 'claude', 'model': 'opus-5-5-1m', 'effort': 'high'},
        'small': {'agent': 'claude', 'model': 'sonnet-5-1m', 'effort': 'medium'},
        'prototype': {'agent': 'claude', 'model': 'sonnet-5-1m', 'effort': 'medium'},
        'review': {'agent': 'codex', 'model': 'gpt-5.6-sol', 'effort': 'high'},
    },
}
POLICY_FILE = Path('.jfactory/coordination.json')


class Refused(Exception):
    pass


def now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def run(tool, *args, stdin=None):
    exe = os.environ.get(f'JFACTORY_{tool.upper()}', tool)
    proc = subprocess.run([exe, *args], input=stdin, capture_output=True, text=True)
    if proc.returncode:
        raise Refused(f'{tool} {" ".join(args[:3])} failed: {proc.stderr.strip() or proc.stdout.strip()}')
    return proc.stdout


def run_json(tool, *args):
    return json.loads(run(tool, *args) or 'null')


def gh(repo, *args):
    return run('gh', *args, '--repo', repo)


def body_file(text):
    handle = tempfile.NamedTemporaryFile('w', suffix='.md', delete=False)
    handle.write(text)
    handle.close()
    return handle.name


# Program state lives in the issue body.

def load(repo, number):
    issue = json.loads(gh(repo, 'issue', 'view', str(number), '--json', 'body,comments,labels,url,state'))
    match = STATE_RE.search(issue['body'] or '')
    if not match:
        raise Refused(f'Issue #{number} is not a jfactory program issue')
    state = json.loads(match.group(1))
    state['_issue'] = issue
    return state


def held(state):
    return any(label['name'] == HOLD_LABEL for label in state['_issue'].get('labels', []))


def render(state):
    lines = [f"# Program: {state['title']}", '']
    if state.get('outcome'):
        lines += [state['outcome'], '']
    lines += ['Coordinated with jfactory. Workers report as comments; the coordinator owns this body.',
              f"Add the `{HOLD_LABEL}` label to stop new launches and tell workers to pause.", '']
    lines += ['## Standing orders', '']
    lines += [f'{i}. {order}' for i, order in enumerate(state['standing'], 1)] or ['None recorded.']
    lines += ['', '## Units', '', '| Unit | State | Role/model | Depends | PR | Head | Workspace | Note |',
              '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for uid, unit in state['units'].items():
        pr = f"#{unit['pr']}" if unit.get('pr') else ''
        link = f"[open]({unit['link']})" if unit.get('link') else ''
        model = f"{unit['role']}: {unit.get('agent', '')}/{unit.get('model', '')}"
        lines.append(f"| {uid} | {unit['state']} | {model} | {', '.join(unit['depends'])} | {pr} | "
                     f"{(unit.get('head') or '')[:7]} | {link} | {cell(unit.get('note'))} |")
    lines += ['', '## Verification ledger', '', '| PR | Head | Verdict | Scopes | Evidence | At |',
              '| --- | --- | --- | --- | --- | --- |']
    lines += [f"| #{r['pr']} | {r['head'][:7]} | {r['verdict']} | {', '.join(r['scopes'])} | "
              f"{cell(r['evidence'])} | {r['at']} |" for r in state['ledger']]
    open_gates = [g for g in state['gates'] if g['status'] == 'open']
    lines += ['', '## Decisions waiting on the owner', '']
    lines += [f"- **{g['id']}** {g['question']} Options: {', '.join(g['options'])}. "
              f"Default: {g['default']}. Waiting: {', '.join(g['units']) or 'none'}." for g in open_gates] or ['None.']
    stored = {k: v for k, v in state.items() if not k.startswith('_')}
    lines += ['', '<!-- jfactory-program', json.dumps(stored, indent=1, sort_keys=True), '-->', '']
    return '\n'.join(lines)


def cell(text):
    return (text or '').replace('|', '/').replace('\n', ' ')[:120]


def save(repo, number, state):
    gh(repo, 'issue', 'edit', str(number), '--body-file', body_file(render(state)))


def comment(repo, number, text):
    gh(repo, 'issue', 'comment', str(number), '--body-file', body_file(text))


def policy(root):
    merged = json.loads(json.dumps(DEFAULT_POLICY))
    path = root / POLICY_FILE
    if path.is_file():
        override = json.loads(path.read_text())
        merged['limit'] = override.get('limit', merged['limit'])
        merged['roles'].update(override.get('roles', {}))
    return merged


def repo_root():
    try:
        out = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], text=True, stderr=subprocess.DEVNULL)
        return Path(out.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


def unit_of(state, uid):
    if uid not in state['units']:
        raise Refused(f'Unknown unit {uid}; known: {", ".join(state["units"]) or "none"}')
    return state['units'][uid]


# Worker reports are append-only comments; the newest report after the coordinator's last change wins.

def fold_reports(state):
    changes = []
    for item in state['_issue'].get('comments', []):
        match = REPORT_RE.search(item.get('body') or '')
        if not match:
            continue
        report = json.loads(match.group(1))
        unit = state['units'].get(report.get('unit'))
        at = report.get('at') or item.get('createdAt', '')
        if not unit or at <= unit.get('updated', '') or report.get('state') not in WORKER_STATES:
            continue
        for key in ('state', 'pr', 'head', 'branch', 'note'):
            if report.get(key) not in (None, ''):
                unit[key] = report[key]
        unit['updated'] = at
        changes.append(f"{report['unit']}: worker reported {report['state']}")
        if report.get('question'):
            gate = add_gate(state, report['question'], ['answer in issue'], 'coordinator decides from records',
                            [report['unit']])
            changes.append(f"{report['unit']}: question parked as {gate['id']}")
    return changes


def add_gate(state, question, options, default, units):
    gate = {'id': f"G{len(state['gates']) + 1}", 'question': question, 'options': options, 'default': default,
            'units': units, 'status': 'open', 'answer': ''}
    state['gates'].append(gate)
    return gate


def refresh_prs(state, repo):
    changes = []
    for uid, unit in state['units'].items():
        if not unit.get('pr') or unit['state'] in TERMINAL:
            continue
        pr = json.loads(gh(repo, 'pr', 'view', str(unit['pr']), '--json', 'state,headRefOid,headRefName'))
        if pr['headRefOid'] != unit.get('head'):
            unit['head'] = pr['headRefOid']
            if unit['state'] == 'verified':
                unit['state'] = 'in-review'
                changes.append(f'{uid}: new head {pr["headRefOid"][:7]} voids its verdict')
        unit['branch'] = pr['headRefName']
        if pr['state'] == 'MERGED':
            unit['state'] = 'merged'
            changes.append(f'{uid}: merged')
        elif pr['state'] == 'CLOSED' and unit['state'] != 'abandoned':
            unit['state'] = 'blocked'
            unit['note'] = 'PR closed without merge'
            changes.append(f'{uid}: PR closed without merge')
    return changes


def session_states(state):
    notes = []
    for uid, unit in state['units'].items():
        if unit['state'] not in ACTIVE or not unit.get('session'):
            continue
        status = run_json('conductor', 'session', 'status', unit['session'], '--json').get('status', 'unknown')
        unit['session_status'] = status
        if status not in ('working', 'running'):
            notes.append(f'{uid}: session is {status} without a final report; read its latest messages')
    return notes


def verdict_at_head(state, unit):
    for row in reversed(state['ledger']):
        if row['pr'] == unit.get('pr') and row['head'] == unit.get('head'):
            return row['verdict']
    return None


def summary(state):
    counts = {s: 0 for s in STATES}
    for unit in state['units'].values():
        counts[unit['state']] += 1
    shown = ', '.join(f'{n} {s}' for s, n in counts.items() if n)
    gates = sum(g['status'] == 'open' for g in state['gates'])
    hold = ' HOLD label set.' if held(state) else ''
    return f"Units: {shown or 'none'}. Open owner decisions: {gates}.{hold}"


# Commands

def cmd_init(args):
    pol = policy(repo_root())
    for name, color, text in [(PROGRAM_LABEL, '5319e7', 'jfactory coordination record'),
                              (HOLD_LABEL, 'b60205', 'Stop new jfactory launches for this program')]:
        gh(args.repo, 'label', 'create', name, '--color', color, '--description', text, '--force')
    standing = [line.strip() for line in Path(args.standing).read_text().splitlines() if line.strip()] \
        if args.standing else []
    state = {'version': 1, 'title': args.title, 'outcome': args.outcome or '', 'base': args.base,
             'repo_url': args.repo_url or f'https://github.com/{args.repo}', 'limit': args.limit or pol['limit'],
             'policy': pol['roles'], 'standing': standing, 'units': {}, 'ledger': [], 'gates': [],
             'created': now()}
    url = gh(args.repo, 'issue', 'create', '--title', f'Program: {args.title}', '--label', PROGRAM_LABEL,
             '--body-file', body_file(render(state))).strip()
    print(url)


def cmd_list(args):
    issues = json.loads(gh(args.repo, 'issue', 'list', '--label', PROGRAM_LABEL, '--state', 'open',
                           '--json', 'number,title,url'))
    for issue in issues:
        print(f"#{issue['number']} {issue['title']} {issue['url']}")
    if not issues:
        print('No open programs.')


def cmd_add(args):
    state = load(args.repo, args.program)
    if args.unit in state['units']:
        raise Refused(f'Unit {args.unit} already exists')
    if args.role not in state['policy']:
        raise Refused(f'Unknown role {args.role}; policy has {", ".join(state["policy"])}')
    missing = [d for d in args.depends if d not in state['units']]
    if missing:
        raise Refused(f'Add dependencies first: {", ".join(missing)}')
    state['units'][args.unit] = {'objective': args.objective, 'role': args.role, 'depends': args.depends,
                                 'paths': args.paths, 'state': 'planned', 'attempts': 0, 'updated': now(),
                                 'note': ''}
    save(args.repo, args.program, state)
    print(summary(state))


def check_brief(text):
    present = {m.group(1) for m in re.finditer(r'^([A-Z]+)\s+\S', text, re.M)}
    return [field for field in BRIEF_FIELDS if field not in present]


def cmd_brief(args):
    missing = check_brief(Path(args.brief).read_text())
    if missing:
        raise Refused('Brief is missing: ' + ', '.join(missing))
    print('Brief has every required field.')


def worker_footer(state, number, uid, repo):
    script = Path(__file__).resolve()
    try:
        script = script.relative_to(repo_root().resolve())
    except ValueError:
        pass
    orders = '\n'.join(f'{i}. {o}' for i, o in enumerate(state['standing'], 1)) or 'None recorded.'
    return f"""

STANDING
{orders}

COORDINATION
You are worker `{uid}` in jfactory program {state['_issue']['url']}. Follow the worker protocol in jfactory's coordination procedure.
Only this unit is yours. Do not edit the program issue body, launch workspaces or change other units' branches.
Report state changes from the repository root; each report is a comment the coordinator reads:
  python3 {script} report --repo {repo} {number} {uid} --state running --note "started"
  python3 {script} report --repo {repo} {number} {uid} --state in-review --pr <number> --head <sha> --note "criteria results and evidence links"
  python3 {script} report --repo {repo} {number} {uid} --state blocked --question "decision you need"
If a report says the program is on hold, stop at a safe boundary, push your work and report.
"""


def cmd_launch(args):
    state = load(args.repo, args.program)
    fold_reports(state)
    refresh_prs(state, args.repo)
    unit = unit_of(state, args.unit)
    if held(state):
        raise Refused(f'Program is on hold ({HOLD_LABEL} label); remove it before launching')
    if unit['state'] not in ('planned', 'failed', 'blocked'):
        raise Refused(f'{args.unit} is {unit["state"]}; only planned, failed or blocked units can launch')
    if unit['attempts'] >= MAX_ATTEMPTS:
        raise Refused(f'{args.unit} already had {unit["attempts"]} attempts; abandon it and replan')
    running = [u for u, v in state['units'].items() if v['state'] in ACTIVE]
    if len(running) >= state['limit']:
        raise Refused(f'Concurrency limit {state["limit"]} reached: {", ".join(running)} running')
    waiting = [d for d in unit['depends'] if state['units'][d]['state'] != 'merged' and d not in args.stack_on]
    if waiting:
        raise Refused(f'Dependencies not merged: {", ".join(waiting)}; wait or pass --stack-on to stack deliberately')
    gates = [g['id'] for g in state['gates'] if g['status'] == 'open' and args.unit in g['units']]
    if gates:
        raise Refused(f'Open owner decisions block {args.unit}: {", ".join(gates)}')
    brief = Path(args.brief).read_text()
    missing = check_brief(brief)
    if missing:
        raise Refused('Brief is missing: ' + ', '.join(missing))
    role = dict(state['policy'][unit['role']])
    for key in ('agent', 'model', 'effort'):
        if getattr(args, key):
            role[key] = getattr(args, key)
    catalog = {a['agent']: a for a in run_json('conductor', 'model', '--json')['agents']}
    agent = catalog.get(role['agent'])
    if not agent or role['model'] not in agent['models']:
        raise Refused(f"{role['agent']}/{role['model']} is not offered by Conductor; run `conductor model`")
    if role.get('effort') and role['effort'] not in agent['efforts']:
        raise Refused(f"Effort {role['effort']} is not offered for {role['agent']}")
    if unit['role'] == 'review':
        same = [d for d in unit['depends'] if state['units'][d].get('agent') == role['agent']]
        if same and not args.allow_same_family:
            raise Refused(f'Reviewer would use the same agent family as {", ".join(same)}; '
                          'choose another agent or pass --allow-same-family and disclose it')
    message = brief.rstrip() + worker_footer(state, args.program, args.unit, args.repo)
    base = state['base']
    if args.stack_on:
        base = unit_of(state, args.stack_on[0]).get('branch')
        if not base:
            raise Refused(f'{args.stack_on[0]} has no pushed branch to stack on yet')
    if args.dry_run:
        print(f"Would launch {args.unit} on {role['agent']}/{role['model']} ({role.get('effort')}) from {base}")
        print(message)
        return
    created = run_json('conductor', 'workspace', 'create', '--repo-url', state['repo_url'], '--branch', base,
                       '--name', f"P{args.program} {args.unit}", '--session-name', args.unit,
                       '--agent', role['agent'], '--model', role['model'], *(['--effort', role['effort']]
                                                                             if role.get('effort') else []),
                       '--message-file', body_file(message), '--json')
    workspace = created.get('workspace', created)
    session = created.get('session') or created.get('firstSession') or {}
    unit.update({'state': 'running', 'attempts': unit['attempts'] + 1, 'updated': now(),
                 'agent': role['agent'], 'model': role['model'], 'effort': role.get('effort'),
                 'workspace': workspace.get('id') or created.get('workspaceId'),
                 'session': session.get('id') or created.get('sessionId'),
                 'link': session.get('deepLink') or workspace.get('deepLink') or created.get('deepLink'),
                 'note': f'attempt {unit["attempts"] + 1}'})
    save(args.repo, args.program, state)
    comment(args.repo, args.program, f"Launched `{args.unit}` on {role['agent']}/{role['model']}: {unit['link']}")
    print(f"Launched {args.unit}: {unit['link']}")


def cmd_report(args):
    state = load(args.repo, args.program)
    unit_of(state, args.unit)
    report = {'unit': args.unit, 'state': args.state, 'pr': args.pr, 'head': args.head, 'note': args.note,
              'question': args.question, 'at': now()}
    text = f"<!-- jfactory-report {json.dumps(report)} -->\n**{args.unit}** reported `{args.state}`"
    if args.pr:
        text += f' for #{args.pr}'
    text += f"\n\n{args.note or ''}"
    if args.question:
        text += f'\n\nDecision needed: {args.question}'
    comment(args.repo, args.program, text)
    print('Reported.')
    if held(state):
        print(f'PROGRAM ON HOLD: stop at a safe boundary, push your work and report {args.unit} as blocked.')


def cmd_sync(args):
    state = load(args.repo, args.program)
    changes = fold_reports(state) + refresh_prs(state, args.repo)
    notes = session_states(state)
    ready = [u for u, v in state['units'].items() if v['state'] == 'planned'
             and all(state['units'][d]['state'] == 'merged' for d in v['depends'])]
    if not args.dry_run:
        save(args.repo, args.program, state)
    print(summary(state))
    print('Changed: ' + ('; '.join(changes) if changes else 'nothing'))
    for note in notes:
        print('Check: ' + note)
    running = sum(v['state'] in ACTIVE for v in state['units'].values())
    slots = max(state['limit'] - running, 0)
    if ready and not held(state):
        print(f"Ready to launch ({slots} free slots): {', '.join(ready)}")


def cmd_set(args):
    state = load(args.repo, args.program)
    unit = unit_of(state, args.unit)
    if args.state == 'verified':
        raise Refused('Record verification with `verdict`, not `set`')
    unit['state'] = args.state
    if args.note:
        unit['note'] = args.note
    unit['updated'] = now()
    save(args.repo, args.program, state)
    print(summary(state))


def cmd_verdict(args):
    state = load(args.repo, args.program)
    unit = unit_of(state, args.unit)
    if not unit.get('pr'):
        raise Refused(f'{args.unit} has no PR yet')
    head = json.loads(gh(args.repo, 'pr', 'view', str(unit['pr']), '--json', 'headRefOid'))['headRefOid']
    if head != args.head:
        raise Refused(f'PR #{unit["pr"]} head is {head[:7]}, not {args.head[:7]}; verify the current head')
    state['ledger'].append({'pr': unit['pr'], 'head': head, 'verdict': args.verdict, 'scopes': args.scopes,
                            'evidence': args.evidence, 'at': now()})
    unit['head'] = head
    unit['state'] = 'verified' if args.verdict == 'verified' else ('failed' if args.verdict == 'failed'
                                                                   else 'in-review')
    unit['updated'] = now()
    save(args.repo, args.program, state)
    print(f'{args.unit} #{unit["pr"]} at {head[:7]}: {args.verdict}')


def cmd_merge(args):
    state = load(args.repo, args.program)
    refresh_prs(state, args.repo)
    unit = unit_of(state, args.unit)
    if verdict_at_head(state, unit) != 'verified':
        raise Refused(f'{args.unit} has no verified verdict at its current head {(unit.get("head") or "")[:7]}')
    gates = [g['id'] for g in state['gates'] if g['status'] == 'open' and args.unit in g['units']]
    if gates:
        raise Refused(f'Open owner decisions block merge: {", ".join(gates)}')
    gh(args.repo, 'pr', 'merge', str(unit['pr']), '--auto', '--squash', '--match-head-commit', unit['head'])
    comment(args.repo, args.program, f"Queued protected auto-merge for `{args.unit}` (#{unit['pr']}) at "
                                     f"{unit['head'][:7]}.")
    save(args.repo, args.program, state)
    print(f'Queued auto-merge for #{unit["pr"]} at {unit["head"][:7]}')


def cmd_gate(args):
    state = load(args.repo, args.program)
    if args.action == 'add':
        for uid in args.units:
            unit_of(state, uid)
        gate = add_gate(state, args.question, args.options, args.default, args.units)
        comment(args.repo, args.program, f"Decision needed ({gate['id']}): {args.question}\n\nOptions: "
                                         f"{', '.join(args.options)}. Default if unanswered: {args.default}.")
        print(gate['id'])
    else:
        gate = next((g for g in state['gates'] if g['id'] == args.id), None)
        if not gate:
            raise Refused(f'Unknown gate {args.id}')
        gate.update({'status': 'resolved', 'answer': args.answer})
        comment(args.repo, args.program, f"Resolved {gate['id']}: {args.answer}")
    save(args.repo, args.program, state)


def cmd_close(args):
    state = load(args.repo, args.program)
    fold_reports(state)
    refresh_prs(state, args.repo)
    open_units = [u for u, v in state['units'].items() if v['state'] not in TERMINAL]
    if open_units:
        raise Refused(f'Units not merged or abandoned: {", ".join(open_units)}')
    save(args.repo, args.program, state)
    gh(args.repo, 'issue', 'close', str(args.program), '--comment', summary(state))
    print('Closed. ' + summary(state))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', help='OWNER/NAME; defaults to the current repository')
    sub = parser.add_subparsers(dest='command', required=True)
    listing = lambda value: [v for v in value.split(',') if v]

    p = sub.add_parser('init', help='Create the program issue')
    p.add_argument('--title', required=True)
    p.add_argument('--outcome')
    p.add_argument('--base', default='main')
    p.add_argument('--limit', type=int)
    p.add_argument('--standing', help='File with one standing order per line')
    p.add_argument('--repo-url')
    p.set_defaults(func=cmd_init)
    p = sub.add_parser('list', help='List open programs')
    p.set_defaults(func=cmd_list)
    p = sub.add_parser('add', help='Add a planned unit')
    p.add_argument('program', type=int)
    p.add_argument('unit')
    p.add_argument('--objective', required=True)
    p.add_argument('--role', default='implement')
    p.add_argument('--depends', type=listing, default=[])
    p.add_argument('--paths', type=listing, default=[])
    p.set_defaults(func=cmd_add)
    p = sub.add_parser('brief', help='Check a task contract for required fields')
    p.add_argument('brief')
    p.set_defaults(func=cmd_brief)
    p = sub.add_parser('launch', help='Create a Conductor workspace for a unit')
    p.add_argument('program', type=int)
    p.add_argument('unit')
    p.add_argument('--brief', required=True)
    p.add_argument('--agent')
    p.add_argument('--model')
    p.add_argument('--effort')
    p.add_argument('--stack-on', type=listing, default=[], help='Unmerged dependency whose branch to start from')
    p.add_argument('--allow-same-family', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    p.set_defaults(func=cmd_launch)
    p = sub.add_parser('report', help='Worker: report this unit\'s state')
    p.add_argument('program', type=int)
    p.add_argument('unit')
    p.add_argument('--state', required=True, choices=sorted(WORKER_STATES))
    p.add_argument('--pr', type=int)
    p.add_argument('--head')
    p.add_argument('--note')
    p.add_argument('--question')
    p.set_defaults(func=cmd_report)
    p = sub.add_parser('sync', help='Fold reports, PRs and sessions into the issue')
    p.add_argument('program', type=int)
    p.add_argument('--dry-run', action='store_true')
    p.set_defaults(func=cmd_sync)
    p = sub.add_parser('set', help='Coordinator: set a unit state')
    p.add_argument('program', type=int)
    p.add_argument('unit')
    p.add_argument('--state', required=True, choices=STATES)
    p.add_argument('--note')
    p.set_defaults(func=cmd_set)
    p = sub.add_parser('verdict', help='Record verification at a PR head')
    p.add_argument('program', type=int)
    p.add_argument('unit')
    p.add_argument('--head', required=True)
    p.add_argument('--verdict', required=True, choices=sorted(VERDICTS))
    p.add_argument('--scopes', type=listing, required=True)
    p.add_argument('--evidence', required=True)
    p.set_defaults(func=cmd_verdict)
    p = sub.add_parser('merge', help='Queue protected auto-merge for a verified unit')
    p.add_argument('program', type=int)
    p.add_argument('unit')
    p.set_defaults(func=cmd_merge)
    p = sub.add_parser('gate', help='Add or resolve an owner decision')
    p.add_argument('action', choices=['add', 'resolve'])
    p.add_argument('program', type=int)
    p.add_argument('--id')
    p.add_argument('--question')
    p.add_argument('--options', type=listing, default=[])
    p.add_argument('--default', default='')
    p.add_argument('--units', type=listing, default=[])
    p.add_argument('--answer')
    p.set_defaults(func=cmd_gate)
    p = sub.add_parser('close', help='Close a finished program')
    p.add_argument('program', type=int)
    p.set_defaults(func=cmd_close)

    args = parser.parse_args(argv)
    try:
        if args.command != 'brief' and not args.repo:
            args.repo = run('gh', 'repo', 'view', '--json', 'nameWithOwner', '--jq', '.nameWithOwner').strip()
        if args.command == 'gate':
            needed = ['question', 'options', 'default'] if args.action == 'add' else ['id', 'answer']
            if not all(getattr(args, n) for n in needed):
                raise Refused(f'gate {args.action} needs --{", --".join(needed)}')
        args.func(args)
    except Refused as error:
        print(f'REFUSED: {error}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
