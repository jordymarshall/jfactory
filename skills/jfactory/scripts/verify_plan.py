#!/usr/bin/env python3
"""Plan verification from changed files and enforce independent verdicts at the PR head.

The repository's `.jfactory/verification.json` maps code paths to feature-map entries and CI
suites. A change touching unmapped files, or the gate itself, needs full verification.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

CONFIG = '.jfactory/verification.json'
CONTEXT = 'jfactory verified'
VERDICT_RE = re.compile(r'<!-- jfactory-verdict (\{.*?\}) -->', re.S)
# Changes to the gate's own inputs can never be scoped down.
GATE_PATHS = ['.jfactory/**', '.github/workflows/**', '.github/rulesets/**']
TRUSTED = {'OWNER', 'MEMBER', 'COLLABORATOR'}
# Each feature declares how much proof its changes need. Unknown values fall back to the strictest level.
LEVELS = ('independent', 'ci')


class Refused(Exception):
    pass


def run(tool, *args):
    exe = os.environ.get(f'JFACTORY_{tool.upper()}', tool)
    try:
        proc = subprocess.run([exe, *args], capture_output=True, text=True)
    except FileNotFoundError:
        raise Refused(f'{tool} is not installed or not on PATH')
    if proc.returncode:
        raise Refused(f'{tool} {" ".join(args[:3])} failed: {proc.stderr.strip() or proc.stdout.strip()}')
    return proc.stdout


@lru_cache(maxsize=None)
def glob_re(pattern):
    out, i = '', 0
    while i < len(pattern):
        if pattern.startswith('**/', i):
            out, i = out + '(?:.*/)?', i + 3
        elif pattern.startswith('**', i):
            out, i = out + '.*', i + 2
        elif pattern[i] == '*':
            out, i = out + '[^/]*', i + 1
        elif pattern[i] == '?':
            out, i = out + '[^/]', i + 1
        else:
            out, i = out + re.escape(pattern[i]), i + 1
    return re.compile(out + r'\Z')


def matches(path, patterns):
    return any(glob_re(p).match(path) for p in patterns)


def load_config(ref=None, root=None):
    if ref:
        text = run('git', 'show', f'{ref}:{CONFIG}')
    else:
        path = Path(root or '.') / CONFIG
        if not path.is_file():
            raise Refused(f'Missing {CONFIG}; create it during setup (see verification.md)')
        text = path.read_text()
    config = json.loads(text)
    for fid, feature in config.get('features', {}).items():
        if not feature.get('paths'):
            raise Refused(f'Feature {fid} in {CONFIG} needs paths')
        if feature.get('verify', 'independent') not in LEVELS:
            raise Refused(f'Feature {fid} in {CONFIG} has verify "{feature["verify"]}"; use independent or ci')
    return config


def plan(files, config):
    features, static, unmapped = set(), [], []
    for path in files:
        if matches(path, GATE_PATHS):
            unmapped.append(path)
            continue
        hit = {fid for fid, f in config.get('features', {}).items() if matches(path, f['paths'])}
        if hit:
            features |= hit
        elif matches(path, config.get('static', [])):
            static.append(path)
        else:
            unmapped.append(path)
    full = bool(unmapped)
    all_features = config.get('features', {})
    if full:
        features = set(all_features)
    suites = set(config.get('always_suites', []))
    for fid in features:
        suites |= set(all_features[fid].get('suites', []))
    if full:
        suites |= set(config.get('full_suites', []))
    static_only = bool(files) and not features and not full
    if static_only:
        suites |= set(config.get('static_suites', []))
    # A change needs an independent verdict unless every affected feature is low risk (`ci`).
    # Unmapped files and gate changes are `full`, which always needs one.
    independent = sorted(f for f in features if all_features[f].get('verify', 'independent') != 'ci')
    if full or independent:
        level = 'independent'
    elif features:
        level = 'ci'
    else:
        level = 'static'
    needs = level == 'independent' or (level == 'static' and config.get('verify_static', False))
    return {'files': len(files), 'features': sorted(features), 'unmapped': unmapped, 'full': full,
            'static_only': static_only, 'suites': sorted(suites), 'level': level,
            'independent_features': independent,
            'needs_verifier': needs,
            'recipes': {fid: all_features[fid].get('recipe', '') for fid in sorted(features)}}


def required_features(result):
    """Features a verdict must cover: all of them for full verification, else the high-risk ones."""
    return result['features'] if result['full'] else result['independent_features']


def render_plan(result):
    if result['static_only']:
        head = 'Static-only change: CI static checks are required; no independent verifier is needed.'
    elif result['level'] == 'ci':
        head = (f"CI-only change: {len(result['features'])} low-risk feature(s); passing CI is required and no "
                'independent verifier is needed.')
    elif result['full']:
        head = (f"Full verification required: {len(result['unmapped'])} changed file(s) are not mapped to a "
                'feature or touch the gate itself.')
    else:
        head = f"Verify {len(result['features'])} affected feature(s)."
    lines = [head, '']
    for fid in result['features']:
        recipe = result['recipes'].get(fid)
        lines.append(f"- `{fid}`" + (f": {recipe}" if recipe else ''))
    if result['unmapped']:
        lines += ['', 'Unmapped: ' + ', '.join(f'`{p}`' for p in result['unmapped'][:20])]
    lines += ['', 'CI suites: ' + (', '.join(result['suites']) or 'none')]
    return '\n'.join(lines)


def git_files(base):
    out = run('git', 'diff', '--name-only', f'{base}...HEAD')
    return [line for line in out.splitlines() if line]


def pr_info(repo, number):
    pr = json.loads(run('gh', 'pr', 'view', str(number), '--repo', repo, '--json',
                        'headRefOid,baseRefName,comments,isCrossRepository,body'))
    files = run('gh', 'api', f'repos/{repo}/pulls/{number}/files', '--paginate', '--jq', '.[].filename')
    pr['files'] = [line for line in files.splitlines() if line]
    return pr


# Model families by agent and by model-name prefix. An identity is `agent/model` or a bare model.
AGENT_FAMILIES = {'claude': 'anthropic', 'codex': 'openai'}
MODEL_FAMILIES = {'claude': 'anthropic', 'opus': 'anthropic', 'sonnet': 'anthropic', 'haiku': 'anthropic',
                  'fable': 'anthropic', 'gpt': 'openai', 'o3': 'openai', 'o4': 'openai', 'codex': 'openai',
                  'grok': 'xai', 'composer': 'cursor', 'gemini': 'google'}


def family(identity):
    """Return the model family of `agent/model` or `model`, or None when it cannot be determined."""
    agent, _, model = (identity or '').strip().lower().rpartition('/')
    for name, fam in MODEL_FAMILIES.items():
        if model.startswith(name):
            return fam
    return AGENT_FAMILIES.get(agent)


def same_family_refusal(verifier, implementer, allowed):
    """Explain why a verdict cannot count as independent, or return None."""
    ours, theirs = family(verifier), family(implementer)
    if not ours or not theirs:
        return f'Cannot tell the model family of verifier {verifier!r} or implementer {implementer!r}; use agent/model'
    if ours == theirs and not allowed:
        return 'Verifier and implementer are the same model family, and the owner has not recorded allow_same_family'
    return None


OBJECTIVE_RE = re.compile(r'^[ \t]*(?:#+[ \t]*objective\b[^\n]*\n(?P<section>(?:(?![ \t]*#)[^\n]*\n?)*)'
                          r'|\**objective\**[ \t]*:[ \t]*(?P<line>[^\n]*))', re.I | re.M)


def states_objective(body):
    """A PR states its objective in a non-empty `Objective` section or an `Objective:` line with content."""
    # Only visible text counts: an objective inside a code fence or an HTML comment is not stated.
    visible = re.sub(r'<!--.*?-->', '', body or '', flags=re.S)
    visible = re.sub(r'^[ \t]*(```|~~~).*?^[ \t]*\1[^\n]*$', '', visible, flags=re.S | re.M)
    for match in OBJECTIVE_RE.finditer(visible + '\n'):
        text = (match.group('section') or match.group('line') or '').strip()
        if len(re.sub(r'\s+', ' ', text)) >= 10:
            return True
    return False


def evaluate(pr, config):
    """Return (state, description) for the jfactory verified status at the PR head."""
    result = plan(pr['files'], config)
    if result['level'] != 'static' and config.get('require_objective', True) and not states_objective(pr.get('body')):
        return 'failure', 'PR does not state its objective: add an "Objective" section or an "Objective:" line'
    if not result['needs_verifier']:
        if result['level'] == 'ci':
            return 'success', 'Low-risk change (verify: ci); required CI checks apply'
        return 'success', 'Static-only change; CI static checks apply'
    head = pr['headRefOid']
    verdicts = []
    for item in pr.get('comments', []):
        # Only accounts with write access to the repository can record a verdict.
        if item.get('authorAssociation') not in TRUSTED:
            continue
        match = VERDICT_RE.search(item.get('body') or '')
        if match:
            try:
                verdicts.append(json.loads(match.group(1)))
            except ValueError:
                continue
    current = [v for v in verdicts if v.get('head') == head]
    if not current:
        return 'failure', f'No verdict for head {head[:7]}'
    verdict = current[-1]
    if verdict.get('verdict') != 'verified':
        return 'failure', f"Latest verdict at {head[:7]} is {verdict.get('verdict')}"
    if result['full'] and not verdict.get('full'):
        return 'failure', 'Full verification required; verdict is not full'
    missing = [f for f in required_features(result) if f not in verdict.get('features', [])]
    if missing and not verdict.get('full'):
        return 'failure', 'Verdict misses features: ' + ', '.join(missing)[:100]
    if not verdict.get('evidence'):
        return 'failure', 'Verdict has no evidence links'
    refusal = same_family_refusal(verdict.get('verifier'), verdict.get('implementer'),
                                  config.get('allow_same_family', False))
    if refusal:
        return 'failure', refusal
    return 'success', f"Verified at {head[:7]} by {verdict.get('verifier')}"


def body_file(text):
    handle = tempfile.NamedTemporaryFile('w', suffix='.md', delete=False)
    handle.write(text)
    handle.close()
    return handle.name


# Commands

def cmd_plan(args):
    config = load_config(args.config_ref)
    files = args.files or git_files(args.base)
    result = plan(files, config)
    print(json.dumps(result, indent=1) if args.json else render_plan(result))


def cmd_check(args):
    pr = pr_info(args.repo, args.pr)
    config = load_config(args.config_ref or f"origin/{pr['baseRefName']}")
    state, description = evaluate(pr, config)
    print(f'{state}: {description}')
    if args.set_status:
        run('gh', 'api', '-X', 'POST', f"repos/{args.repo}/statuses/{pr['headRefOid']}",
            '-f', f'state={state}', '-f', f'context={CONTEXT}', '-f', f'description={description[:140]}',
            *(['-f', f'target_url={args.target_url}'] if args.target_url else []))
    return 0 if state == 'success' or args.set_status else 1


def cmd_verdict(args):
    pr = pr_info(args.repo, args.pr)
    if pr['headRefOid'] != args.head:
        raise Refused(f"PR #{args.pr} head is {pr['headRefOid'][:7]}, not {args.head[:7]}; verify the current head")
    config = load_config(args.config_ref or f"origin/{pr['baseRefName']}")
    # Refuse here anything the status would reject, so a verdict that cannot count is never posted.
    refusal = same_family_refusal(args.verifier, args.implementer, config.get('allow_same_family', False))
    if refusal:
        raise Refused(refusal)
    result = plan(pr['files'], config)
    features = args.features or required_features(result)
    missing = [f for f in required_features(result) if f not in features]
    if args.verdict == 'verified' and (missing or (result['full'] and not args.full)):
        raise Refused('A verified verdict must cover ' + (
            'the full feature map (--full)' if result['full'] else 'features: ' + ', '.join(missing)))
    record = {'head': args.head, 'verdict': args.verdict, 'features': sorted(features), 'full': args.full,
              'verifier': args.verifier, 'implementer': args.implementer, 'evidence': args.evidence,
              'at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
    text = (f"<!-- jfactory-verdict {json.dumps(record)} -->\n**Verification {args.verdict}** at `{args.head[:7]}` "
            f"by {args.verifier} (implementer {args.implementer}).\n\nFeatures: "
            f"{'full feature map' if args.full else ', '.join(features) or 'none'}\n\nEvidence:\n"
            + '\n'.join(f'- {e}' for e in args.evidence) + (f'\n\n{args.note}' if args.note else ''))
    run('gh', 'pr', 'comment', str(args.pr), '--repo', args.repo, '--body-file', body_file(text))
    print(f'Posted {args.verdict} verdict for #{args.pr} at {args.head[:7]}')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', help='OWNER/NAME; defaults to the current repository')
    parser.add_argument('--config-ref', help='Git ref to read the mapping from, e.g. origin/main')
    sub = parser.add_subparsers(dest='command', required=True)
    listing = lambda value: [v for v in value.split(',') if v]

    p = sub.add_parser('plan', help='Show affected features and CI suites for a change')
    p.add_argument('--base', default='origin/main')
    p.add_argument('--files', type=listing, help='Comma-separated paths instead of git diff')
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=cmd_plan)
    p = sub.add_parser('check', help='Evaluate the jfactory verified status for a PR')
    p.add_argument('--pr', type=int, required=True)
    p.add_argument('--set-status', action='store_true', help='Publish the result as a commit status')
    p.add_argument('--target-url')
    p.set_defaults(func=cmd_check)
    p = sub.add_parser('verdict', help='Verifier: post a verdict for the PR head')
    p.add_argument('--pr', type=int, required=True)
    p.add_argument('--head', required=True)
    p.add_argument('--verdict', required=True, choices=['verified', 'failed', 'blocked', 'partially-verified'])
    p.add_argument('--verifier', required=True, help='agent/model, e.g. codex/gpt-6-luna')
    p.add_argument('--implementer', required=True, help='agent/model, e.g. claude/opus-5-5-1m')
    p.add_argument('--features', type=listing, default=[])
    p.add_argument('--full', action='store_true')
    p.add_argument('--evidence', action='append', default=[], required=True)
    p.add_argument('--note')
    p.set_defaults(func=cmd_verdict)

    args = parser.parse_args(argv)
    try:
        if args.command != 'plan' and not args.repo:
            args.repo = run('gh', 'repo', 'view', '--json', 'nameWithOwner', '--jq', '.nameWithOwner').strip()
        return args.func(args) or 0
    except Refused as error:
        print(f'REFUSED: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
