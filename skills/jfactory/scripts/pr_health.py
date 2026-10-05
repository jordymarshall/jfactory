#!/usr/bin/env python3
"""Find pull requests that stopped moving, say the one next step for each, and do the safe mechanical ones.

This is plain Python and `gh`. It uses no AI model, so it costs nothing to run every 30 minutes from a scheduled
workflow (templates/jfactory-pr-health.yml). For each open, non-draft PR into the default branch it reads CI, the
`jfactory verified` status, the verdicts at the head and GitHub's merge state, and gives the PR one state:

  conflict       the branch conflicts with the base branch
  ci-failed      a CI check failed at the head
  partial        the latest verdict at the head is partially-verified, blocked or failed
  behind         the branch is behind the base branch, and the repository requires it to be current
  no-ci          no CI check ran at the head after --verdict-hours
  ci-running     CI is still running (not reported)
  needs-verdict  CI is green, the gate still waits, and no verdict exists at the head after --verdict-hours
  gate-failed    a verified verdict exists at the head, but the jfactory verified status still fails
  not-queued     everything passes, but auto-merge is not queued
  waiting        a young PR waits for its verdict (not reported)
  ready          verified, green and auto-merge queued (not reported)
  idle           a not-reported state, but nothing happened (commit, check or comment) for --idle-hours

With --act it does two safe things, each at most once per PR head, and it keeps the report issue:

  - A `behind` PR with a verified verdict at its head: ask GitHub to merge the base branch into it (update-branch).
    One PR per check, oldest first (a merge train).
  - A CI failure that is only infrastructure (cancelled, startup failure, the runner was lost, or the job never ran
    a step): re-run the failed jobs. It never re-runs a test failure.

The report is one issue labelled jfactory-pr-health ("Stuck PRs"). The tool edits it in place and never comments,
closes it when nothing is stuck and reopens it when something is. The issue body also holds the record of done
actions, so the next run does not repeat one. Without --act the tool changes nothing: it reads the issue, prints
the table and says which actions it would take.

  pr_health.py --repo OWNER/NAME [--act] [--verdict-hours 1] [--idle-hours 6]

Exit status is 0, or 2 when gh fails.
"""
import os
import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_plan as vp  # noqa: E402

LABEL = 'jfactory-pr-health'
TITLE = 'Stuck PRs'
STATE_RE = re.compile(r'<!-- jfactory-pr-health-state (\{.*?\}) -->', re.S)
FIELDS = ('number,title,isDraft,headRefOid,mergeStateStatus,autoMergeRequest,createdAt,comments,'
          'statusCheckRollup')
QUIET = {'ready', 'ci-running', 'waiting'}
GATE_WORKFLOW = 'jfactory verified'
# STALE: GitHub replaced the check with a newer one.
PASSING = {'SUCCESS', 'SKIPPED', 'NEUTRAL', 'STALE'}
# Job conclusions that are never a test result.
INFRA_CONCLUSIONS = {'CANCELLED', 'STARTUP_FAILURE'}
# Messages GitHub writes when the machine, not the code, failed.
INFRA_MESSAGES = re.compile(r'lost communication with the server|The job was not started|received a shutdown signal|'
                            r'runner .* (?:was|has been) (?:deleted|removed)|The operation was canceled', re.I)
SETUP_STEP = 'Set up job'
JOB_URL = re.compile(r'/actions/runs/(\d+)/job/(\d+)')


def as_writer(fn, *args):
    """Run one write with JFACTORY_WRITE_TOKEN when it is set. Reads use GH_TOKEN (the workflow's built-in token, which
    can read check and status results). A fine-grained token often cannot read them ("Resource not accessible by
    personal access token" on statusCheckRollup), but only such a token makes GitHub start CI on the merge commit
    that update-branch creates."""
    token = os.environ.get('JFACTORY_WRITE_TOKEN')
    if not token:
        return fn(*args)
    old = os.environ.get('GH_TOKEN')
    os.environ['GH_TOKEN'] = token
    try:
        return fn(*args)
    finally:
        if old is None:
            os.environ.pop('GH_TOKEN', None)
        else:
            os.environ['GH_TOKEN'] = old


def when(text):
    """A GitHub timestamp as an aware datetime; None for missing or GitHub's zero date."""
    if not text or text.startswith('0001-'):
        return None
    return datetime.fromisoformat(text.replace('Z', '+00:00'))


def hours(delta):
    return delta.total_seconds() / 3600


def span(delta):
    total = int(delta.total_seconds() // 60)
    if total < 60:
        return f'{total} min'
    if total < 48 * 60:
        return f'{total // 60} h'
    return f'{total // (24 * 60)} days'


def latest_checks(pr):
    """CI check runs at the head, newest per workflow and job, without the gate's own job."""
    newest = {}
    for item in pr.get('statusCheckRollup') or []:
        if item.get('__typename') != 'CheckRun':
            continue
        if item.get('workflowName') == GATE_WORKFLOW or item.get('name') in vp.GATE_JOBS:
            continue
        key = (item.get('workflowName'), item.get('name'))
        if key not in newest or (item.get('startedAt') or '') >= (newest[key].get('startedAt') or ''):
            newest[key] = item
    return list(newest.values())


def gate_state(pr):
    """The `jfactory verified` commit status at the head (SUCCESS, FAILURE, PENDING ...), or None."""
    states = [i.get('state') for i in pr.get('statusCheckRollup') or []
              if i.get('__typename') == 'StatusContext' and i.get('context') == vp.CONTEXT]
    return states[-1] if states else None


def last_activity(pr):
    """The newest check or comment on the PR. A push starts checks, so a new commit shows up as a check."""
    times = [when(pr.get('createdAt'))]
    times += [when(c.get('createdAt')) for c in pr.get('comments') or []]
    for item in pr.get('statusCheckRollup') or []:
        times += [when(item.get('startedAt')), when(item.get('completedAt'))]
    return max(t for t in times if t)


def job_failure(repo, check):
    """Classify one failed check run: ('infra', why) or ('test', why). A failed step other than job set-up is a
    test failure, whatever else happened."""
    name = check.get('name')
    conclusion = (check.get('conclusion') or '').upper()
    match = JOB_URL.search(check.get('detailsUrl') or '')
    if not match:
        return 'test', f'{name} ({conclusion.lower()}; not a GitHub Actions job, so it is not re-run)'
    job = json.loads(vp.run('gh', 'api', f'repos/{repo}/actions/jobs/{match.group(2)}'))
    steps = job.get('steps') or []
    failed = [s['name'] for s in steps if s.get('conclusion') == 'failure' and s.get('name') != SETUP_STEP]
    if failed:
        return 'test', f'{name}: step "{failed[0]}" failed'
    if conclusion in INFRA_CONCLUSIONS:
        return 'infra', f'{name} ({conclusion.lower()})'
    if not any(s.get('started_at') for s in steps if s.get('name') != SETUP_STEP):
        return 'infra', f'{name} (no step ran)'
    notes = json.loads(vp.run('gh', 'api', f'repos/{repo}/check-runs/{match.group(2)}/annotations'))
    note = next((n.get('message', '') for n in notes if INFRA_MESSAGES.search(n.get('message') or '')), None)
    if note:
        return 'infra', f'{name} ({note.splitlines()[0][:80]})'
    return 'test', f'{name} ({conclusion.lower()})'


def first_line(record):
    evidence = record.get('evidence') or []
    text = evidence[0] if isinstance(evidence, list) and evidence else str(evidence or '')
    return (text.strip().splitlines() or ['no evidence given'])[0][:120]


def classify(repo, pr, now, verdict_hours=1, idle_hours=6):
    """Return a dict with the PR's state, the time since its last activity, the next step and the action it
    allows ('update' or 'rerun', with the run ids), or none."""
    head = pr['headRefOid']
    idle = now - last_activity(pr)
    out = {'number': pr['number'], 'title': pr.get('title', ''), 'head': head, 'idle': idle, 'action': None,
           'queued': bool(pr.get('autoMergeRequest'))}
    checks = latest_checks(pr)
    failed = [c for c in checks if (c.get('status') or '').upper() == 'COMPLETED'
              and (c.get('conclusion') or '').upper() not in PASSING]
    running = sorted(c['name'] for c in checks if (c.get('status') or '').upper() != 'COMPLETED')
    verdicts = [v for v in vp.trusted_verdicts(pr) if v.get('head') == head]
    verdict = verdicts[-1] if verdicts else None
    gate = gate_state(pr)
    merge_state = (pr.get('mergeStateStatus') or '').upper()

    def state(name, step, action=None):
        out.update(state=name, step=step, action=action)
        return out

    if merge_state == 'DIRTY':
        return state('conflict', 'Author: merge the base branch into the PR branch and resolve the conflicts.')
    if failed:
        kinds = [job_failure(repo, c) for c in failed]
        tests = [why for kind, why in kinds if kind == 'test']
        if tests:
            return state('ci-failed', 'Author: fix the failing check: ' + '; '.join(tests[:3]) + '.')
        runs = sorted({JOB_URL.search(c['detailsUrl']).group(1) for c in failed})
        return state('ci-failed', 'Infrastructure failure, not a test: ' + '; '.join(w for _, w in kinds[:3])
                     + '. Re-run the failed jobs once.', ('rerun', runs))
    if verdict and verdict.get('verdict') in ('partially-verified', 'blocked', 'failed'):
        said = first_line(verdict)
        kind = verdict['verdict']
        if kind == 'partially-verified':
            step = ('Verifier: produce the proof the gate needs (walkthrough and screenshots for changed screens), '
                    'or post blocked and name what blocks it.')
        elif kind == 'blocked':
            step = 'Owner or coordinator: remove what blocks the verifier, then ask for a new verdict.'
        elif vp.verdict_cause(verdict) in ('rules', 'both'):
            step = 'Owner: decide about the rule the verifier says is wrong.'
        else:
            step = 'Author: fix what the verifier found, then ask for a re-check with --since.'
        return state('partial', f'{step} Verdict ({kind}): "{said}"')
    if merge_state == 'BEHIND':
        if verdict and verdict.get('verdict') == 'verified':
            return state('behind', f'Merge the base branch into the PR (verified at {head[:7]}); then the verifier '
                                   f're-checks only the merge with --since {head[:7]}.', ('update', None))
        return state('behind', 'Author: merge the base branch into the PR branch, so the verdict covers the final head.')
    if not checks and hours(idle) >= verdict_hours:
        return state('no-ci', f'No CI check ran at head {head[:7]}. Push a commit or start CI by hand. If this check '
                              'merged the base branch, set the JFACTORY_PR_HEALTH_TOKEN secret, so CI starts on its '
                              'merge commits.')
    if running:
        if hours(idle) > idle_hours:
            return state('idle', f'CI has not moved for {span(idle)}: {", ".join(running[:3])}. Check for a queued '
                                 'job with no runner.')
        return state('ci-running', 'Wait for CI.')
    if gate != 'SUCCESS':
        if verdict and verdict.get('verdict') == 'verified':
            return state('gate-failed', f'Verifier: the jfactory verified status is {(gate or "missing").lower()} '
                                        f'although a verified verdict exists at {head[:7]}. Read the status message '
                                        'on the PR and post the verdict it asks for.')
        green_at = max([when(c.get('completedAt')) for c in checks if when(c.get('completedAt'))]
                       + [when(pr.get('createdAt'))], default=now)
        if hours(now - green_at) >= verdict_hours:
            return state('needs-verdict', f'Verifier: post a verdict for head {head[:7]}. CI is green since '
                                          f'{span(now - green_at)} ago.')
        out_state = 'waiting'
    elif not pr.get('autoMergeRequest'):
        return state('not-queued', f'Implementer: if the change is done, queue auto-merge '
                                   f'(gh pr merge {pr["number"]} --auto --squash).')
    else:
        out_state = 'ready'
    if hours(idle) > idle_hours:
        what = ('Auto-merge is queued, but the PR did not merge. Check the merge gates on the PR.' if out_state == 'ready'
                else 'Nothing happened. The coordinator or owner checks who owns this PR.')
        return state('idle', what)
    return state(out_state, 'Wait.')


# The report issue


def find_issue(repo):
    found = json.loads(vp.run('gh', 'issue', 'list', '--repo', repo, '--label', LABEL, '--state', 'all',
                              '--json', 'number,state', '--limit', '1'))
    if not found:
        return None
    number = str(found[0]['number'])
    return {'number': number, **json.loads(vp.run('gh', 'issue', 'view', number, '--repo', repo,
                                                  '--json', 'body,state'))}


def read_state(issue):
    match = STATE_RE.search((issue or {}).get('body') or '')
    try:
        return json.loads(match.group(1)) if match else {}
    except ValueError:
        return {}


def table(results):
    stuck = [r for r in results if r['state'] not in QUIET]
    if not stuck:
        return 'No stuck PRs.', stuck
    lines = ['| PR | State | No activity for | Next step |', '| --- | --- | --- | --- |']
    for r in stuck:
        title = r['title'].replace('|', '\\|')[:60]
        lines.append(f"| #{r['number']} {title} | {r['state']} | {span(r['idle'])} | {r['step'].replace('|', '/')} |")
    return '\n'.join(lines), stuck


QUEUE_ALERT_MINUTES = 30


def queue_health(repo, now):
    """The CI queue: workflow runs waiting for a runner and the oldest wait in minutes. A long queue means the jobs
    started per hour exceed the runners (references/ci-runners.md, queue operations); it is reported, not fixed here."""
    runs = []
    for status in ('queued', 'waiting', 'pending'):
        runs += json.loads(vp.run('gh', 'run', 'list', '--repo', repo, '--status', status, '--limit', '100',
                                  '--json', 'databaseId,createdAt'))
    if not runs:
        return {'runs': 0, 'oldest_minutes': 0}
    oldest = min(when(r['createdAt']) for r in runs)
    return {'runs': len({r['databaseId'] for r in runs}), 'oldest_minutes': int((now - oldest).total_seconds() // 60)}


def report(results, actions, now, state, queue=None):
    text, stuck = table(results)
    lines = [f'# {TITLE}', '',
             f'The scheduled stuck-PR check (`pr_health.py`, no AI model) wrote this at {now:%Y-%m-%d %H:%M} UTC. '
             'It runs every 30 minutes, edits this issue in place and closes it when no PR is stuck.', '', text]
    if queue and queue['oldest_minutes'] >= QUEUE_ALERT_MINUTES:
        stuck = True
        lines += ['', f"**CI queue:** {queue['runs']} workflow runs are waiting; the oldest has waited "
                      f"{queue['oldest_minutes']} minutes. Cut jobs before adding machines: see "
                      '`references/ci-runners.md#queue-operations-fewer-jobs-before-more-machines`.']
    if actions:
        lines += ['', 'Actions this run:'] + [f'- {a}' for a in actions]
    lines += ['', f'<!-- jfactory-pr-health-state {json.dumps(state, sort_keys=True)} -->']
    return '\n'.join(lines) + '\n', bool(stuck)


def publish(repo, issue, body, stuck):
    """Create, edit, close or reopen the one report issue. It never comments."""
    if issue is None:
        if not stuck:
            return 'nothing stuck; no issue'
        vp.run('gh', 'label', 'create', LABEL, '--repo', repo, '--color', 'D93F0B', '--force',
               '--description', 'Open PRs that stopped moving (scheduled stuck-PR check)')
        vp.run('gh', 'issue', 'create', '--repo', repo, '--title', TITLE, '--label', LABEL,
               '--body-file', vp.body_file(body))
        return 'opened'
    number, open_now = issue['number'], (issue.get('state') or '').upper() == 'OPEN'
    if (issue.get('body') or '') != body:
        vp.run('gh', 'issue', 'edit', number, '--repo', repo, '--body-file', vp.body_file(body))
    if stuck and not open_now:
        vp.run('gh', 'issue', 'reopen', number, '--repo', repo)
        return 'reopened'
    if not stuck and open_now:
        vp.run('gh', 'issue', 'close', number, '--repo', repo, '--reason', 'completed')
        return 'closed'
    return 'updated' if stuck else 'closed already'


def act(repo, result, done, now, dry=False):
    """Do the result's safe action once per head. Returns a line for the report, or None. A dry run only says
    what it would do."""
    kind = (result.get('action') or (None,))[0]
    if not kind:
        return None
    key = f"{kind}:{result['number']}:{result['head']}"
    if key in done:
        if kind == 'rerun':
            result['step'] = ('Infrastructure failure again after one re-run at this head. A person checks the '
                              'runners and re-runs the jobs.')
        else:
            result['step'] = 'The update was already requested for this head. Check the PR for an error.'
        return None
    if dry:
        return f"#{result['number']}: would {'merge the base branch into the PR' if kind == 'update' else 're-run the failed jobs'} (dry run)."
    if kind == 'update':
        as_writer(vp.run, 'gh', 'api', '-X', 'PUT', f"repos/{repo}/pulls/{result['number']}/update-branch",
                  '-f', f"expected_head_sha={result['head']}")
        line = f"#{result['number']}: merged the base branch into the PR (it was verified at {result['head'][:7]})."
    else:
        for run_id in result['action'][1]:
            vp.run('gh', 'run', 'rerun', run_id, '--failed', '--repo', repo)
        line = f"#{result['number']}: re-ran the failed jobs once (run {', '.join(result['action'][1])})."
    done[key] = now.strftime('%Y-%m-%dT%H:%M:%SZ')
    result['step'] += ' Done by this check; it will not repeat it for this head.'
    return line


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--act', action='store_true', help='do the safe actions and keep the report issue')
    parser.add_argument('--verdict-hours', type=float, default=1)
    parser.add_argument('--idle-hours', type=float, default=6)
    parser.add_argument('--now', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    now = when(args.now) if args.now else datetime.now(timezone.utc)
    try:
        base = json.loads(vp.run('gh', 'api', f'repos/{args.repo}'))['default_branch']
        prs = json.loads(vp.run('gh', 'pr', 'list', '--repo', args.repo, '--base', base, '--state', 'open',
                                '--limit', '100', '--json', FIELDS))
        results = [classify(args.repo, pr, now, args.verdict_hours, args.idle_hours)
                   for pr in prs if not pr.get('isDraft')]
        issue = find_issue(args.repo)
        state = read_state(issue)
        heads = {f"{r['number']}:{r['head']}" for r in results}
        done = {k: v for k, v in state.get('done', {}).items() if k.split(':', 1)[1] in heads}
        actions = []
        # Merge train: one PR holds the merge slot at a time, across checks. A PR is in the slot while auto-merge is
        # queued and it is not behind, conflicted or failing, which includes a PR this check updated earlier whose
        # new CI is still running. Only when the slot is free does the oldest verified behind PR get the base branch.
        # Updating every behind PR at once starts N CI runs for one merge slot.
        in_slot = next((r for r in sorted(results, key=lambda r: r['number']) if r.get('queued')
                        and r.get('state') not in ('behind', 'conflict', 'ci-failed', 'partial')), None)
        updating = in_slot is not None
        for result in sorted(results, key=lambda r: r['number']):
            if (result.get('action') or (None,))[0] == 'update':
                if updating:
                    holder = in_slot or updating_now
                    result['step'] = (f"Waits its turn: #{holder['number']} holds the merge slot; one PR catches up "
                                      'with the base branch at a time.')
                    continue
                updating, updating_now = True, result
            line = act(args.repo, result, done, now, dry=not args.act)
            if line:
                actions.append(line)
        body, stuck = report(results, actions, now, {'done': done}, queue_health(args.repo, now))
        print(body.split('\n<!-- jfactory-pr-health-state')[0])
        if args.act:
            print('Issue: ' + publish(args.repo, issue, body, stuck))
    except (vp.Refused, ValueError, KeyError) as error:
        print(f'REFUSED: {error}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
