#!/usr/bin/env python3
"""Check the checkers: sample recently merged PRs and report where verification fell short of "done means right".

The gates enforce the rules on each PR; this looks back across many, so a gap in the gates themselves (a rule that
stopped being enforced, a verifier that stopped citing the standards, screen changes merged without anyone looking)
shows up as a pattern instead of going unnoticed. Findings for a PR:

- merged without a verified verdict at its final commit when its plan needed one;
- a verdict that names no standards, when the repository has a standards map;
- a screen change merged without reviewed screenshots;
- a description that names no outcomes/<job>.md document, or has no "Why it's right" section, when outcomes exist;
- anything else the required status would reject today, judged by the gate's own code.

It also counts merged PRs whose history includes a verdict saying a rule (not the change) was wrong, and lists rules
flagged on more than one PR, so a recurring bad rule surfaces instead of being argued again on every PR.

  method_audit.py --repo OWNER/NAME [--limit 20] [--since YYYY-MM-DD] [--issue]

It judges every PR by today's rules and the base branch's current map. --since limits it to recent merges, so a rule
added later is not applied to PRs merged before it; the report says so either way. Exit status 1 means findings. --issue opens or updates an issue labelled
jfactory-method-audit with the report.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_plan as vp  # noqa: E402

LABEL = 'jfactory-method-audit'


def audit_pr(pr, config):
    """Findings for one merged PR: whatever the required status would reject at its final commit today, judged by
    the same code as the gate (CI results aside, since CI ran before the merge)."""
    state, description = vp.evaluate(pr, config)
    if state == 'success':
        return []
    if description.startswith('No verdict for head'):
        description = 'merged without a verified verdict at its final commit'
    return [description]


def rule_flags(pr):
    """The rules a verifier said were wrong anywhere in this PR's history: (rule location, full text) pairs."""
    flags = []
    for verdict in vp.trusted_verdicts(pr):
        if vp.verdict_cause(verdict) in ('rules', 'both'):
            for text in verdict.get('rule_changes') or []:
                flags.append((vp.rule_source(text) or text[:80], text))
    return flags


def repeated_rules(results):
    """Rules flagged on more than one merged PR, most flagged first: {location: [PR numbers]}."""
    seen = {}
    for pr, _ in results:
        for where in {where for where, _ in rule_flags(pr)}:
            seen.setdefault(where, []).append(pr['number'])
    return dict(sorted(((w, n) for w, n in seen.items() if len(n) > 1), key=lambda kv: -len(kv[1])))


def report(results, limit, since=None):
    flagged = [(pr, found) for pr, found in results if found]
    scope = f'the {limit} PRs merged since {since}' if since else f'the last {limit} merged PRs'
    lines = [f'Method audit of {scope}: {len(flagged)} with findings.',
             '', 'Each PR is judged by the gate\'s own rules as they are today. A PR merged before a rule existed can show '
             'it; read those as history, not as a new gap.', '']
    ruled = [pr for pr, _ in results if rule_flags(pr)]
    repeated = repeated_rules(results)
    lines += [f'Rule problems: {len(ruled)} of {limit} merged PRs had a verdict saying a rule, not the change, was '
              'wrong' + (' (' + ', '.join(f"#{pr['number']}" for pr in ruled) + ').' if ruled else '.')]
    if repeated:
        lines += ['', 'Rules flagged on more than one PR. Each is a candidate for a standing fix: bring it to the owner '
                      'with the verifiers\' proposals rather than letting each PR argue it again.', '']
        lines += [f"- `{where}`: " + ', '.join(f'#{n}' for n in numbers) for where, numbers in repeated.items()]
    lines += ['']
    counts = {}
    for _, found in flagged:
        for item in found:
            counts[item] = counts.get(item, 0) + 1
    lines += [f'- {n}× {item}' for item, n in sorted(counts.items(), key=lambda kv: -kv[1])]
    if flagged:
        lines += ['', '| PR | Findings |', '| --- | --- |']
        lines += [f"| #{pr['number']} {pr.get('title', '')[:60]} | {'; '.join(found)} |" for pr, found in flagged]
        lines += ['', 'Each repeated finding is a gap in the gates or the verifier contract: fix it at the strongest '
                      'layer of the correction ladder (references/methodology.md), not by reminding agents.']
    return '\n'.join(lines)


def publish(repo, text, clean):
    """Open, update or close the audit issue. Repeating the same report adds nothing; a clean run closes it."""
    existing = vp.run('gh', 'issue', 'list', '--repo', repo, '--label', LABEL, '--state', 'open', '--json', 'number',
                      '--jq', '.[0].number // empty').strip()
    if not existing:
        if clean:
            return 'clean; no issue'
        vp.run('gh', 'label', 'create', LABEL, '--repo', repo, '--color', 'B60205', '--force',
               '--description', 'Verification fell short of done means right in merged PRs')
        vp.run('gh', 'issue', 'create', '--repo', repo, '--title', 'Method audit: verification gaps in merged PRs',
               '--label', LABEL, '--body-file', vp.body_file(text))
        return 'opened'
    last = vp.run('gh', 'issue', 'view', existing, '--repo', repo, '--json', 'body,comments',
                  '--jq', '(.comments | last | .body) // .body').strip()
    if last != text.strip():
        vp.run('gh', 'issue', 'comment', existing, '--repo', repo, '--body-file', vp.body_file(text))
    elif not clean:
        return 'unchanged'
    if clean:
        # Close even when this report was already posted: an earlier close may have failed after its comment.
        vp.run('gh', 'issue', 'close', existing, '--repo', repo, '--reason', 'completed')
        return 'closed'
    return 'updated'



def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--base', default='main', help='branch whose current map the PRs are judged against')
    parser.add_argument('--issue', action='store_true', help='open or update an issue labelled ' + LABEL)
    parser.add_argument('--since', help='only PRs merged on or after this date (YYYY-MM-DD), so newer rules are not '
                                        'applied to older merges')
    args = parser.parse_args(argv)
    try:
        config = vp.load_config(f'origin/{args.base}')
        search = ['--search', f'merged:>={args.since}'] if args.since else []
        numbers = json.loads(vp.run('gh', 'pr', 'list', '--repo', args.repo, '--state', 'merged', '--base', args.base,
                                    '--limit', str(args.limit), *search, '--json', 'number'))
        results = []
        for item in numbers:
            pr = vp.pr_info(args.repo, item['number'])
            pr['number'] = item['number']
            results.append((pr, audit_pr(pr, config)))
    except vp.Refused as error:
        print(f'REFUSED: {error}', file=sys.stderr)
        return 2
    text = report(results, len(results), args.since)
    print(text)
    # A rule flagged again and again is a gap in the method too, so it keeps the audit issue open.
    clean = not any(found for _, found in results) and not repeated_rules(results)
    if args.issue:
        publish(args.repo, text, clean)
    return 0 if clean else 1


if __name__ == '__main__':
    raise SystemExit(main())
