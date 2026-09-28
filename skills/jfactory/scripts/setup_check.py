#!/usr/bin/env python3
"""Check that a repository's jfactory setup is complete and that its setup record tells the truth.

Run from the repository root after setup, after an update and whenever setup is re-run. It checks the
artifacts setup must leave behind and rejects readiness claims the evidence does not support, such as
product direction marked verified while owner interview questions are unanswered. With --remote it also
reads the GitHub settings that protected auto-merge depends on.

Exit status: 0 complete, 1 something must be fixed, 3 consistent but blocked on named owner steps.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_plan  # noqa: E402

AREAS = ['Documentation', 'Product direction', 'Workspace tools', 'Verification', 'Environments', 'PR delivery']
STATES = {'verified', 'configured but unverified', 'blocked', 'not run by request', 'not applicable'}
DONE = {'verified', 'not applicable'}
ENTRY_SECTIONS = {'product brief': 'Product brief', 'system map': 'System map',
                  'feature/status map': 'Feature/status map', 'agent instructions': 'Agent instructions'}
MERGE_TARGETS = {'staging', 'none', 'production'}
UNANSWERED = {'', 'unanswered', 'tbd', 'todo', '?'}
# The interview must cover each topic in templates/setup-record.md, not just any one question.
INTERVIEW_TOPICS = {'who it is for': r'\bwho\b', 'what they do today': r'\btoday\b|instead|workaround',
                    'the outcome and how to measure it': r'outcome|improv|success|measure',
                    'what is out of scope': r'out of scope|non-goal|exclud',
                    'the next objective': r'next .*objective|first .*objective'}


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, text):
        self.items.append((level, text))

    def count(self, level):
        return sum(1 for item in self.items if item[0] == level)


def sections(text):
    """Map each `## ` heading (lower case) to the text under it."""
    found, current = {}, None
    for line in text.splitlines():
        if line.startswith('## '):
            current = line[3:].strip().lower()
            found[current] = []
        elif current is not None:
            found[current].append(line)
    return {name: '\n'.join(lines) for name, lines in found.items()}


def table_rows(text):
    rows = []
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
        if line.strip().startswith('|') and not set(''.join(cells)) <= set('-: '):
            rows.append(cells)
    return rows[1:]  # skip the header row


def check_entry(root, entry, report):
    path = root / entry
    if not path.is_file():
        report.add('FAIL', f'{entry} is missing; setup keeps the agent entry point there')
        return
    headings = [name.lower() for name in sections(path.read_text())]
    missing = [label for key, label in ENTRY_SECTIONS.items() if not any(key in h for h in headings)]
    if missing:
        report.add('FAIL', f'{entry} lacks the entry sections: {", ".join(missing)} (see references/setup.md step 2)')
    else:
        report.add('PASS', f'{entry} has the product brief, system map, feature/status map and agent instructions')


def check_record(root, record, report):
    """Validate the setup record and return its readiness states."""
    path = root / record
    if not path.is_file():
        report.add('FAIL', f'Setup record {record} is missing; copy templates/setup-record.md and fill it in')
        return {}
    parts = sections(path.read_text())
    states = {}
    for row in table_rows(parts.get('readiness', '')):
        if row and row[0] in AREAS:
            states[row[0]] = row[1].strip('`').lower() if len(row) > 1 else ''
            if len(row) < 3 or not row[2] or row[2].startswith('<'):
                report.add('FAIL', f'Readiness "{row[0]}" has no evidence or reason')
    for area in AREAS:
        if area not in states:
            report.add('FAIL', f'Readiness table has no "{area}" row')
        elif states[area] not in STATES:
            report.add('FAIL', f'Readiness "{area}" has state "{states[area]}"; use one of: {", ".join(sorted(STATES))}')
    if states.get('PR delivery') == 'not applicable':
        report.add('FAIL', 'PR delivery cannot be "not applicable": jfactory delivers through protected PRs. '
                           'Use "blocked" with the missing step when the repository has no PR host yet')

    interview = table_rows(parts.get('owner interview', ''))
    if not interview:
        report.add('FAIL', 'Setup record has no "Owner interview" table; setup must ask the owner, not infer the product')
    else:
        missing = [topic for topic, pattern in INTERVIEW_TOPICS.items()
                   if not any(re.search(pattern, row[0], re.I) for row in interview)]
        if missing:
            report.add('FAIL', 'Owner interview does not ask about: ' + ', '.join(missing) +
                               ' (use the questions in templates/setup-record.md)')
        open_rows = [row[0] for row in interview if len(row) < 2 or row[1].lower() in UNANSWERED]
        product = states.get('Product direction')
        if open_rows and product == 'verified':
            report.add('FAIL', 'Product direction is "verified" but the owner has not answered: ' + '; '.join(open_rows))
        elif len(open_rows) == len(interview) and product not in (None, 'blocked', 'not run by request'):
            report.add('FAIL', 'No interview question has an owner answer, so product direction must be "blocked" '
                               'until the owner replies')
        elif open_rows:
            report.add('WARN', f'{len(open_rows)} interview question(s) await the owner: ' + '; '.join(open_rows))
        else:
            report.add('PASS', f'Owner answered all {len(interview)} interview questions')

    location = re.search(r'^Task location:\s*(.+)$', parts.get('next objective', ''), re.M)
    if not location or location.group(1).strip().startswith('<'):
        report.add('FAIL', 'Setup record does not name the task location under "Next objective" '
                           '("Task location: ..."); objectives need a findable home')
    else:
        report.add('PASS', f'Task location: {location.group(1).strip()}')
    return states


def check_verification(root, report, states):
    try:
        config = verify_plan.load_config(root=root)
    except (verify_plan.Refused, ValueError) as error:
        report.add('FAIL', f'Verification map: {error}')
        config = None
    if config is not None:
        try:
            tracked = subprocess.run(['git', '-C', str(root), 'ls-files'], capture_output=True, text=True,
                                     check=True).stdout.split()
        except (subprocess.CalledProcessError, FileNotFoundError) as error:
            report.add('FAIL', f'Cannot list tracked files with git ({error}), so map coverage is unchecked')
            tracked = None
    if config is not None:
        features = config.get('features', {})
        unset = sorted(f for f, v in features.items() if 'verify' not in v)
        low = sorted(f for f, v in features.items() if v.get('verify') == 'ci')
        if unset:
            report.add('WARN', f'{len(unset)} feature(s) have no risk level and default to independent verification: '
                               f'{", ".join(unset[:8])}. Agree "verify": "independent" or "ci" with the owner')
        else:
            report.add('PASS', f'Risk levels set: {len(features) - len(low)} independent, {len(low)} CI-only'
                               + (f' ({", ".join(low)})' if low else ''))
    if config is not None and tracked is not None:
        result = verify_plan.plan(tracked, config)
        unmapped = [p for p in result['unmapped'] if not verify_plan.matches(p, verify_plan.GATE_PATHS)]
        if unmapped:
            report.add('WARN', f'{len(unmapped)} tracked file(s) match no feature or static pattern and will force '
                               f'full verification: {", ".join(unmapped[:8])}')
        else:
            report.add('PASS', f'.jfactory/verification.json maps every tracked file '
                               f'({len(config.get("features", {}))} features)')
    workflows = root / '.github' / 'workflows'
    gate = [p for p in workflows.glob('*.y*ml') if 'verify_plan.py' in p.read_text() and ' check ' in p.read_text()] \
        if workflows.is_dir() else []
    if gate:
        report.add('PASS', f'The jfactory verified workflow is installed: {gate[0].relative_to(root)}')
    else:
        report.add('FAIL', 'No workflow runs `verify_plan.py ... check`; install templates/jfactory-verified.yml')


def check_delivery(root, report, states):
    path = root / '.jfactory' / 'coordination.json'
    target = json.loads(path.read_text()).get('merge_deploys') if path.is_file() else None
    if target not in MERGE_TARGETS:
        report.add('FAIL', 'Record what merging deploys as "merge_deploys" (staging, none or production) in '
                           '.jfactory/coordination.json')
    elif target == 'production':
        level = 'FAIL' if states.get('PR delivery') == 'verified' else 'WARN'
        report.add(level, 'Merging releases production, so auto-merge must stay off until releases go to staging or '
                          'nowhere; PR delivery cannot be verified')
    else:
        report.add('PASS', f'Merging deploys to: {target}')


def check_remote(repo, branch, report, states):
    try:
        info = json.loads(verify_plan.run('gh', 'api', f'repos/{repo}'))
        branch = branch or info.get('default_branch', 'main')
        rules = json.loads(verify_plan.run('gh', 'api', f'repos/{repo}/rules/branches/{branch}'))
    except (verify_plan.Refused, ValueError) as error:
        level = 'FAIL' if states.get('PR delivery') == 'verified' else 'WARN'
        report.add(level, f'Could not read GitHub settings ({error}); PR delivery cannot be confirmed')
        return False
    contexts = {c.get('context') for r in rules if r.get('type') == 'required_status_checks'
                for c in r.get('parameters', {}).get('required_status_checks', [])}
    needs_pr = any(r.get('type') == 'pull_request' for r in rules)
    try:
        classic = json.loads(verify_plan.run('gh', 'api', f'repos/{repo}/branches/{branch}/protection'))
        contexts |= set((classic.get('required_status_checks') or {}).get('contexts') or [])
        needs_pr = needs_pr or bool(classic.get('required_pull_request_reviews'))
    except (verify_plan.Refused, ValueError):
        pass  # no classic branch protection
    gaps = []
    if not info.get('allow_auto_merge'):
        gaps.append('"Allow auto-merge" is off (Settings > General > Pull Requests)')
    if not needs_pr:
        gaps.append(f'{branch} does not require pull requests')
    if verify_plan.CONTEXT not in contexts:
        gaps.append(f'{branch} does not require the "{verify_plan.CONTEXT}" status')
    if not contexts - {verify_plan.CONTEXT}:
        gaps.append(f'{branch} requires no CI check besides "{verify_plan.CONTEXT}"')
    if gaps:
        level = 'FAIL' if states.get('PR delivery') == 'verified' else 'WARN'
        report.add(level, 'Protected auto-merge is not fully enforced: ' + '; '.join(gaps) +
                   ' (apply templates/ruleset-main.json; see references/auto-merge.md)')
        return False
    report.add('PASS', f'GitHub requires PRs and {", ".join(sorted(contexts))} on {branch}; auto-merge is allowed')
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', default='.', help='repository root (default: current directory)')
    parser.add_argument('--entry', help='agent entry file (default: AGENTS.md, or CLAUDE.md when only that exists)')
    parser.add_argument('--record', default='.jfactory/setup.md', help='setup record path')
    parser.add_argument('--remote', action='store_true', help='also check GitHub auto-merge and required checks')
    parser.add_argument('--repo', help='OWNER/NAME for --remote (default: the current repository)')
    parser.add_argument('--branch', help='protected branch for --remote (default: the repository default branch)')
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    entry = args.entry or ('CLAUDE.md' if not (root / 'AGENTS.md').exists() and (root / 'CLAUDE.md').exists()
                           else 'AGENTS.md')
    report = Report()
    check_entry(root, entry, report)
    states = check_record(root, args.record, report)
    check_verification(root, report, states)
    check_delivery(root, report, states)
    remote_ok = False
    if args.remote:
        repo = args.repo
        if not repo:
            try:
                repo = verify_plan.run('gh', 'repo', 'view', '--json', 'nameWithOwner', '--jq', '.nameWithOwner').strip()
            except verify_plan.Refused as error:
                level = 'FAIL' if states.get('PR delivery') == 'verified' else 'WARN'
                report.add(level, f'Could not identify the GitHub repository: {error}')
        if repo:
            remote_ok = check_remote(repo, args.branch, report, states)
    else:
        report.add('INFO', 'GitHub settings not checked; rerun with --remote before calling PR delivery verified')

    for level, text in report.items:
        print(f'{level}: {text}')
    pending = [f'{area} ({state})' for area, state in states.items() if state not in DONE]
    if states.get('PR delivery') == 'verified' and not remote_ok:
        pending.append('PR delivery (GitHub gates not confirmed in this run; rerun with --remote)')
    if report.count('FAIL'):
        print(f'\nSetup is not consistent: fix {report.count("FAIL")} item(s) above before reporting readiness.')
        return 1
    if pending:
        print('\nSetup is consistent but incomplete. Open areas: ' + ', '.join(pending) +
              '. Report each with its owner step.')
        return 3
    print('\nSetup is complete.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
