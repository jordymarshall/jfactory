#!/usr/bin/env python3
"""Check the checkers: sample recently merged PRs and report where verification fell short of "done means right".

The gates enforce the rules on each PR; this looks back across many, so a gap in the gates themselves (a rule that
stopped being enforced, a verifier that stopped citing the standards, screen changes merged without anyone looking)
shows up as a pattern instead of going unnoticed. Findings for a PR:

- merged without a verified verdict at its final commit when its plan needed one;
- a verdict that names no standards, when the repository has a standards map;
- a screen change merged without reviewed screenshots;
- a description that names no outcomes/ document, or has no "Why it's right" section, when outcomes exist.

  method_audit.py --repo OWNER/NAME [--limit 20] [--issue]

It judges every PR against the base branch's current map, which may be stricter than the one the PR merged under;
read old findings with that in mind. Exit status 1 means findings. --issue opens or updates an issue labelled
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
    """Findings for one merged PR, judged against `config`."""
    result = vp.plan(pr['files'], config)
    if result['level'] == 'static':
        return []
    findings = []
    body = pr.get('body') or ''
    outcomes = [s for s in config.get('_standards', []) if s.startswith('outcomes/')]
    if outcomes and not any(doc in body for doc in outcomes):
        findings.append('description names no outcomes/ document')
    if outcomes and "why it's right" not in body.lower().replace('’', "'"):
        findings.append('description has no "Why it\'s right" section')
    if not result['needs_verifier']:
        return findings
    verdicts = [v for v in vp.trusted_verdicts(pr) if v.get('head') == pr['headRefOid']]
    verdict = verdicts[-1] if verdicts else None
    if not verdict or verdict.get('verdict') != 'verified':
        return findings + ['merged without a verified verdict at its final commit']
    if vp.needs_standards(result, config) and not verdict.get('standards'):
        findings.append('verdict names no standards')
    if vp.needs_screenshots(result, config) and not verdict.get('screenshots'):
        findings.append('screen change merged without reviewed screenshots')
    if not verdict.get('evidence'):
        findings.append('verdict has no evidence links')
    return findings


def report(results, limit):
    flagged = [(pr, found) for pr, found in results if found]
    lines = [f'Method audit of the last {limit} merged PRs: {len(flagged)} with findings.', '']
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
    existing = vp.run('gh', 'issue', 'list', '--repo', repo, '--label', LABEL, '--state', 'open', '--json', 'number',
                      '--jq', '.[0].number // empty').strip()
    body = vp.body_file(text)
    if existing:
        vp.run('gh', 'issue', 'comment', existing, '--repo', repo, '--body-file', body)
    elif not clean:
        vp.run('gh', 'issue', 'create', '--repo', repo, '--title', 'Method audit: verification gaps in merged PRs',
               '--label', LABEL, '--body-file', body)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--base', default='main', help='branch whose current map the PRs are judged against')
    parser.add_argument('--issue', action='store_true', help='open or update an issue labelled ' + LABEL)
    args = parser.parse_args(argv)
    try:
        config = vp.load_config(f'origin/{args.base}')
        numbers = json.loads(vp.run('gh', 'pr', 'list', '--repo', args.repo, '--state', 'merged', '--base', args.base,
                                    '--limit', str(args.limit), '--json', 'number'))
        results = []
        for item in numbers:
            pr = vp.pr_info(args.repo, item['number'])
            pr['number'] = item['number']
            results.append((pr, audit_pr(pr, config)))
    except vp.Refused as error:
        print(f'REFUSED: {error}', file=sys.stderr)
        return 2
    text = report(results, len(results))
    print(text)
    clean = not any(found for _, found in results)
    if args.issue:
        publish(args.repo, text, clean)
    return 0 if clean else 1


if __name__ == '__main__':
    raise SystemExit(main())
