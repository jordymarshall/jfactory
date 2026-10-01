#!/usr/bin/env python3
"""Check that a repository's jfactory setup is complete and that its setup record tells the truth.

Run from the repository root after setup, after an update and whenever setup is re-run. It checks the
artifacts setup must leave behind and rejects readiness claims the evidence does not support, such as
product direction marked verified while owner interview questions are unanswered, or merges that
deploy to staging with no recorded way to release production. With --remote it also
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
# The release record in coordination.json; references/release.md explains each field.
RELEASE_FIELDS = ['production', 'revision', 'promote', 'rollback']
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
        for level, text in verify_plan.audit(tracked, config, root):
            report.add(level, f'Map: {text}')
    if config is not None:
        check_targets(root, config, report, states)
    workflows = root / '.github' / 'workflows'
    gate = [p for p in workflows.glob('*.y*ml') if 'verify_plan.py' in p.read_text() and ' check ' in p.read_text()] \
        if workflows.is_dir() else []
    if config is not None:
        journeys = sorted(n for n, d in config.get('suites', {}).items() if d.get('target'))
        total = verify_plan.cost(set(config.get('suites', {})), config)[0]
        budget = config.get('pr_budget_minutes')
        planned = [p for p in workflows.glob('*.y*ml') if re.search(r'verify_plan\.py"?\s+(ci|plan)\b', p.read_text())] \
            if workflows.is_dir() else []
        over = isinstance(budget, (int, float)) and total > budget
        if (journeys or over) and not planned:
            reason = f'journey suites ({", ".join(journeys[:4])})' if journeys else f'{total} min of suites'
            report.add('FAIL', f'The map has {reason} but no workflow runs `verify_plan.py ci`, so CI would run '
                               'everything on every PR; install templates/jfactory-checks.yml')
        live = verify_plan.live_suites(config)
        scheduled = [p for p in workflows.glob('*.y*ml')
                     if re.search(r'verify_plan\.py"?\s+ci\b[^\n]*--live', p.read_text())] if workflows.is_dir() else []
        if live and not scheduled:
            report.add('FAIL', f'Live-model suite(s) {", ".join(live)} never run on PRs, and no workflow runs '
                               '`verify_plan.py ci --live`, so nothing exercises them; install '
                               'templates/jfactory-live-suites.yml')
    if gate and not re.search(r'^\s*checks:\s*read\b', gate[0].read_text(), re.M):
        report.add('FAIL', f'{gate[0].relative_to(root)} lacks `checks: read`, so the status cannot confirm CI passed '
                           'at the verified head; update it from templates/jfactory-verified.yml')
    elif gate:
        report.add('PASS', f'The jfactory verified workflow is installed: {gate[0].relative_to(root)}')
    else:
        report.add('FAIL', 'No workflow runs `verify_plan.py ... check`; install templates/jfactory-verified.yml')
    # An audit counts only if a scheduled workflow executes the script in a `run:` step, not one that mentions it.
    audits = [p for p in workflows.glob('*.y*ml') if runs_method_audit(p.read_text())] if workflows.is_dir() else []
    if audits:
        report.add('PASS', f'The method audit checks the checkers: {audits[0].relative_to(root)}')
    else:
        report.add('FAIL' if states.get('PR delivery') == 'verified' else 'WARN',
                   'No workflow runs `method_audit.py`, so nothing notices when verification stops meeting "done '
                   'means right" across merged PRs; install templates/jfactory-method-audit.yml')


def check_targets(root, config, report, states):
    """Each target must have started and answered where verification runs, shown by a `smoke` receipt."""
    targets = config.get('targets', {})
    if not targets:
        return
    path = root / '.jfactory' / 'smoke.json'
    receipts = json.loads(path.read_text()) if path.is_file() else {}
    level = 'FAIL' if states.get('Verification') == 'verified' else 'WARN'
    for name in targets:
        receipt = receipts.get(name)
        if not receipt or not receipt.get('ok'):
            failed = next((s for s in (receipt or {}).get('steps', []) if not s.get('ok') and 'attempt' not in s), None)
            report.add(level, f'Target {name} has no passing start-up receipt'
                       + (f' (failed at {failed["step"]}: {failed["detail"]})' if failed else '')
                       + f'; run `verify_plan.py smoke --target {name} --fresh --record .jfactory/smoke.json` '
                         'in a new workspace')
        elif not receipt.get('fresh'):
            report.add(level, f'Target {name} started only in an existing checkout; rerun smoke with --fresh in a new '
                               'workspace so a verifier\'s workspace is known to work')
        else:
            report.add('PASS', f'Target {name} started in a fresh workspace at {receipt.get("commit", "")[:7]} '
                               f'on {receipt.get("at", "?")}')


def run_blocks(text):
    """The shell script of each `run:` step: the inline value (unquoted if YAML-quoted), or the indented block below
    `run: |` / `run: >-`."""
    lines, blocks = text.splitlines(), []
    for i, line in enumerate(lines):
        match = re.match(r'^(\s*)(-\s+)?run:\s*(.*)$', line)
        if not match:
            continue
        indent, value = len(match.group(1)) + len(match.group(2) or ''), match.group(3).strip()
        if value and value[0] not in '|>':
            if len(value) > 1 and value[0] == value[-1] == "'":
                value = value[1:-1].replace("''", "'")
            elif len(value) > 1 and value[0] == value[-1] == '"':
                try:
                    value = json.loads(value)
                except ValueError:
                    value = value[1:-1]
            blocks.append(value)
            continue
        block, margin = [], None
        for follow in lines[i + 1:]:
            if follow.strip() and len(follow) - len(follow.lstrip()) <= indent:
                break
            if margin is None and follow.strip():
                margin = len(follow) - len(follow.lstrip(' '))
            block.append(follow)
        # Remove only the YAML block indentation: other leading and trailing space is part of the script.
        block = [line[margin or 0:] for line in block]
        blocks.append((' ' if value.startswith('>') else '\n').join(block))
    return blocks


def shell_commands(script):
    """Each simple command in a shell script as its words, read the way the shell reads them: quotes and backslashes
    keep operators literal, a quoted string may span lines, and comments and here-document bodies run nothing. A
    script with an unclosed quote fails before running, so it yields no commands."""
    commands, words, word, heredocs = [], [], None, []
    i, n = 0, len(script)

    def finish_word():
        nonlocal word
        if word is not None:
            words.append(word)
            word = None

    def finish_command():
        nonlocal words
        finish_word()
        if words:
            commands.append(words)
        words = []

    while i < n:
        c = script[i]
        if c == '\\':
            if script[i + 1:i + 2] != '\n':
                word = (word or '') + script[i + 1:i + 2]
            i += 2
        elif c == "'":
            end = script.find("'", i + 1)
            if end < 0:
                return []
            word, i = (word or '') + script[i + 1:end], end + 1
        elif c == '"':
            j, text = i + 1, ''
            while j < n and script[j] != '"':
                if script[j] == '\\' and j + 1 < n:
                    j += 1
                text, j = text + script[j], j + 1
            if j >= n:
                return []
            word, i = (word or '') + text, j + 1
        elif c == '#' and word is None:
            end = script.find('\n', i)
            i = n if end < 0 else end
        elif c == '<' and script.startswith('<<', i) and not script.startswith('<<<', i):
            finish_word()
            match = re.compile(r'<<(-?)[ \t]*([\'"]?)([^\s\'";&|()<>]+)\2').match(script, i)
            if not match:
                return []
            heredocs.append((match.group(3), bool(match.group(1))))
            i = match.end()
        elif c == '\n':
            finish_command()
            i += 1
            # A here-document ends only at a line that is exactly its delimiter; <<- also strips leading tabs.
            for delimiter, tabs in heredocs:
                while i < n:
                    end = script.find('\n', i)
                    line = script[i:n if end < 0 else end]
                    i = n if end < 0 else end + 1
                    if (line.lstrip('\t') if tabs else line) == delimiter:
                        break
            heredocs = []
        elif c in ' \t':
            finish_word()
            i += 1
        elif c in ';&|()`':
            finish_command()
            i += 1
        else:
            word, i = (word or '') + c, i + 1
    finish_command()
    return commands


def runs_method_audit(text):
    """A scheduled workflow with a run step that executes `python3 ... method_audit.py`."""
    scheduled = re.search(r'(?m)^\s*schedule:\s*$', text) and re.search(r'(?m)^\s*-\s*cron:', text)

    def audits(words):
        while words and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*', words[0]):
            words = words[1:]
        if not words or not re.fullmatch(r'(\S*/)?python3?', words[0]):
            return False
        script = next((w for w in words[1:] if not w.startswith('-')), '')
        return script.endswith('method_audit.py')

    return bool(scheduled) and any(audits(c) for script in run_blocks(text) for c in shell_commands(script))


def check_standards(root, report, states):
    """The standards map names each quality dimension's source of truth, and every source it names exists."""
    path = root / verify_plan.STANDARDS
    level = 'FAIL' if states.get('Documentation') == 'verified' else 'WARN'
    if not path.is_file():
        report.add(level, f'No standards map at {verify_plan.STANDARDS}: verifiers have no source of truth to check '
                          'changes against. Create it from templates/standards.md (references/setup.md)')
        return
    if not (root / 'outcomes' / 'README.md').is_file():
        report.add(level, 'No outcomes/README.md: the customer, the outcomes that matter and the non-goals every change '
                          'is judged against. Create it from templates/outcomes-readme.md (references/setup.md)')
    rows = verify_plan.parse_standards(path.read_text())
    missing = [d for d in verify_plan.STANDARD_DIMENSIONS if d not in rows]
    if missing:
        report.add(level, 'Standards map lacks dimension(s): ' + '; '.join(missing))
    vague = [d for d, row in rows.items() if not row['paths'] and not row['none']]
    if vague:
        report.add(level, 'Standards map rows need a backticked source path, or "none" and why: ' + '; '.join(vague))
    unproven = [d for d, row in rows.items() if not row['check'].strip()]
    if unproven:
        report.add(level, 'Standards map rows need a "How changes are checked" entry that says how it is proven: '
                   + '; '.join(unproven))
    outside = sorted({p[1:] for row in rows.values() for p in row['paths'] if p.startswith('!')})
    if outside:
        report.add('FAIL', 'Standards map names source(s) outside the repository: ' + ', '.join(outside))
    absent = sorted({p for row in rows.values() for p in row['paths'] if not p.startswith('!') and not (root / p).exists()})
    if absent:
        report.add('FAIL', 'Standards map names source(s) that do not exist: ' + ', '.join(absent))
    sources = {p for row in rows.values() for p in row['paths']}
    # A document outside the map that still claims authority misleads agents and verifiers alike.
    claims = []
    try:
        tracked = subprocess.run(['git', '-C', str(root), 'ls-files', '*.md'], capture_output=True, text=True,
                                 check=True).stdout.split()
    except (subprocess.CalledProcessError, FileNotFoundError):
        tracked = []
    for name in tracked:
        if name in sources or name.startswith(('.jfactory/', '.agents/', '.claude/', '.cursor/', 'skills/', 'vendor/')):
            continue
        try:
            head = (root / name).read_text(errors='replace')[:3000]
        except OSError:
            continue
        # An affirmative claim ("this document is the source of truth", "this spec wins"), not a denial, and not
        # in a document that carries an explicit superseded, historical or archived notice.
        claim = re.search(r'\b(this|the)\s+(document|file|spec|specification|page)\s+(is|remains)\s+(the\s+)?'
                          r'(single\s+|canonical\s+|only\s+)?source\s+of\s+truth|\bthis\s+(one|document|spec)\s+wins\b',
                          head, re.I)
        notice = re.search(r'(?im)^\s*(>\s*)?(\*\*)?\s*(status\s*:\s*)?(superseded|historical|archived|deprecated)(\*\*)?'
                           r'\s*(:|\u2014|-|\.|$)|\b(this|the)\s+(document|file|spec|specification|page)\s+(is|was)\s+'
                           r'(now\s+)?(superseded|historical|archived|deprecated)\b|\bsuperseded\s+by\b', head)
        if claim and not notice:
            claims.append(name)
    if claims:
        report.add('WARN', 'Document(s) outside the standards map claim to be the source of truth without a '
                           'superseded or historical note: ' + ', '.join(claims[:8]))
    if not missing and not vague and not unproven and not absent:
        report.add('PASS', f'Standards map covers {len(rows)} dimensions with {len(sources)} source document(s)')


def check_delivery(root, report, states):
    path = root / '.jfactory' / 'coordination.json'
    config = json.loads(path.read_text()) if path.is_file() else {}
    target = config.get('merge_deploys')
    if target not in MERGE_TARGETS:
        report.add('FAIL', 'Record what merging deploys as "merge_deploys" (staging, none or production) in '
                           '.jfactory/coordination.json')
    elif target == 'production':
        level = 'FAIL' if states.get('PR delivery') == 'verified' else 'WARN'
        report.add(level, 'Merging releases production, so auto-merge must stay off until releases go to staging or '
                          'nowhere; PR delivery cannot be verified')
    else:
        report.add('PASS', f'Merging deploys to: {target}')
        check_release(config, target, report, states)


def check_release(config, target, report, states):
    """Check that the path from staging to production is recorded, so a release request has steps to follow."""
    release = config.get('release')
    if release is None and target == 'none':
        return  # nothing deploys on merge; a release record is optional
    fields = RELEASE_FIELDS + (['staging'] if target == 'staging' else [])
    release = release if isinstance(release, dict) else {}
    missing = [f for f in fields if not isinstance(release.get(f), str) or not release[f].strip()
               or release[f].strip().startswith('<')]
    if missing:
        level = 'FAIL' if states.get('PR delivery') == 'verified' else 'WARN'
        report.add(level, 'The release procedure is incomplete: record ' + ', '.join(f'"{f}"' for f in missing) +
                          ' under "release" in .jfactory/coordination.json (see references/release.md)')
        return
    report.add('PASS', 'Release procedure recorded: ' + ', '.join(fields))
    if not str(release.get('approval') or '').strip():
        report.add('WARN', 'No "approval" gate is recorded for production, so only instructions stop an early '
                           'release; protect the production environment where the host allows it')


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
    check_standards(root, report, states)
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
    print('\nSetup is complete: every check here passes. These checks confirm the records exist and agree; whether '
          'the outcomes, job goals and standards are right is for the owner and the verifiers to judge.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
