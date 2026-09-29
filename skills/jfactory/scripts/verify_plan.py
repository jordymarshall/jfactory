#!/usr/bin/env python3
"""Plan verification from changed files, run only the suites a change needs, and enforce independent verdicts.

The repository's `.jfactory/verification.json` maps code paths to feature-map entries and CI
suites. `audit` checks the map covers the repository, `ci` runs the planned suites, `smoke` proves the
app starts where verification runs. A change touching unmapped files, or the gate itself, needs a full verdict.
"""
import argparse
import json
import os
import platform
import re
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
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


def plan(files, config, impact=None):
    """Plan a change. `impact` maps suites to the files they executed (from `load_impact`); it only adds suites."""
    features, static, unmapped, gate = set(), [], [], []
    for path in files:
        if matches(path, GATE_PATHS):
            gate.append(path)
            continue
        hit = {fid for fid, f in config.get('features', {}).items() if matches(path, f['paths'])}
        if hit:
            features |= hit
        elif matches(path, config.get('static', [])):
            static.append(path)
        else:
            unmapped.append(path)
    # Unmapped code could affect anything, so it pulls in every feature. A gate-only change needs a full
    # verdict (a reviewer reads the gate change) but only the fast full_suites, never every feature's journeys.
    full = bool(unmapped or gate)
    all_features = config.get('features', {})
    if unmapped:
        features = set(all_features)
    suites = set(config.get('always_suites', []))
    for fid in features:
        suites |= set(all_features[fid].get('suites', []))
    if full:
        suites |= set(config.get('full_suites', []))
    static_only = bool(files) and not features and not full
    if static_only:
        suites |= set(config.get('static_suites', []))
    # Coverage from earlier runs adds every suite that executed a changed file, so shared code runs the
    # journeys that really use it. It never removes a suite the map requires.
    because = {}
    for suite, executed in (impact or {}).items():
        if suite in config.get('suites', {}):
            hits = sorted(p for p in files if p in executed)
            if hits and suite not in suites:
                because[suite] = hits
                suites.add(suite)
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
    minutes, untimed = cost(suites, config)
    shards = shard_count(config)
    return {'files': len(files), 'features': sorted(features), 'unmapped': unmapped, 'gate': gate, 'full': full,
            'static_only': static_only, 'suites': sorted(suites), 'level': level,
            'independent_features': independent,
            'needs_verifier': needs, 'minutes': minutes, 'untimed_suites': untimed,
            'budget_minutes': config.get('pr_budget_minutes'), 'impact': because, 'shards': shards,
            'wall_minutes': max((cost(b, config)[0] for b in binpack(suites, config, shards)), default=0),
            'recipes': {fid: all_features[fid].get('recipe', '') for fid in sorted(features)}}


def minutes_of(config, suite):
    value = config.get('suites', {}).get(suite, {}).get('minutes')
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def cost(suites, config):
    """Estimate CI minutes from each suite's measured `minutes`; also return the suites with no timing."""
    known = {s: minutes_of(config, s) for s in suites}
    return sum(m for m in known.values() if m), sorted(s for s, m in known.items() if m is None)


def shard_count(config):
    value = config.get('shards', 1)
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else 1


def binpack(suites, config, n):
    """Split suites into n groups of similar total minutes, longest first, so parallel CI jobs finish together."""
    bins = [[] for _ in range(n)]
    totals = [0.0] * n
    for suite in sorted(suites, key=lambda s: (-(minutes_of(config, s) or 0), s)):
        i = totals.index(min(totals))
        bins[i].append(suite)
        totals[i] += minutes_of(config, suite) or 0
    return bins


def coverage_files(path, root):
    """Repository files a coverage report says were executed. Reads Istanbul `coverage-final.json`, V8
    (`NODE_V8_COVERAGE` or Playwright `page.coverage`), coverage.py `coverage json`, or a plain list of paths."""
    root = Path(root).resolve()
    found = set()

    def add(name):
        if not name:
            return
        if name.startswith('file://'):
            name = urllib.request.url2pathname(name[7:])
        candidate = Path(name)
        if candidate.is_absolute():
            try:
                candidate = candidate.resolve().relative_to(root)
            except ValueError:
                return
        found.add(candidate.as_posix())

    text = Path(path).read_text(errors='replace')
    try:
        data = json.loads(text)
    except ValueError:
        for line in text.splitlines():
            add(line.strip())
        return found
    entries = data.get('result') if isinstance(data, dict) and 'result' in data else data
    # A file counts when one of its functions ran. Module top-level code runs whenever the file loads, often at
    # startup for every journey, so it alone does not tie a file to a journey; the map still covers such files.
    if isinstance(entries, list):  # V8: [{url, functions: [{functionName, ranges: [{count}]}]}], first is top level
        for entry in entries:
            if any(fn.get('ranges') and fn['ranges'][0].get('count', 0) > 0 for fn in entry.get('functions', [])[1:]):
                add(entry.get('url'))
    elif isinstance(data, dict) and isinstance(data.get('files'), dict):  # coverage.py
        for name, info in data['files'].items():
            if info.get('executed_lines'):
                add(name)
    elif isinstance(data, dict):  # Istanbul: {path: {s: {id: count}}}
        for name, info in data.items():
            counts = info.get('f') or info.get('s', {}) if isinstance(info, dict) else {}
            if any(v > 0 for v in counts.values()):
                add(info.get('path', name))
    return found


def load_impact(path):
    """Read impact records (a file, or a directory of them) into {suite: set(files)}. Missing means none yet."""
    target = Path(path)
    records = sorted(target.rglob('*.json')) if target.is_dir() else [target] if target.is_file() else []
    merged = {}
    for record in records:
        try:
            data = json.loads(record.read_text())
        except ValueError:
            continue
        for suite, files in data.get('suites', {}).items():
            merged.setdefault(suite, set()).update(files)
    return merged


def required_features(result):
    """Features a verdict must cover: all of them for full verification, else the high-risk ones."""
    return result['features'] if result['full'] else result['independent_features']


def render_plan(result):
    if result['static_only']:
        head = 'Static-only change: CI static checks are required; no independent verifier is needed.'
    elif result['level'] == 'ci':
        head = (f"CI-only change: {len(result['features'])} low-risk feature(s); passing CI is required and no "
                'independent verifier is needed.')
    elif result['unmapped']:
        head = (f"Full verification required: {len(result['unmapped'])} changed file(s) are not mapped to a "
                'feature. Map them in .jfactory/verification.json; `ci` refuses to run until they are.')
    elif result['full']:
        head = (f"Gate change: {len(result['gate'])} file(s) change the verification gate. The verdict must be "
                f"--full: review the gate change and run the recipes it alters. Verify {len(result['features'])} "
                'affected feature(s).')
    else:
        head = f"Verify {len(result['features'])} affected feature(s)."
    lines = [head, '']
    for fid in result['features']:
        recipe = result['recipes'].get(fid)
        lines.append(f"- `{fid}`" + (f": {recipe}" if recipe else ''))
    if result['unmapped']:
        lines += ['', 'Unmapped: ' + ', '.join(f'`{p}`' for p in result['unmapped'][:20])]
    if result['gate']:
        lines += ['', 'Gate: ' + ', '.join(f'`{p}`' for p in result['gate'][:20])]
    if result['impact']:
        lines += ['', 'Added from recorded coverage:'] + [
            f"- `{suite}` executes {', '.join(f'`{p}`' for p in files[:5])}" for suite, files in result['impact'].items()]
    lines += ['', 'CI suites: ' + (', '.join(result['suites']) or 'none')]
    estimate = f"Estimated CI time: {result['minutes']} min"
    if result['shards'] > 1:
        estimate += f", about {result['wall_minutes']} min across {result['shards']} parallel jobs"
    if result['untimed_suites']:
        estimate += f" plus untimed {', '.join(result['untimed_suites'])}"
    if result['budget_minutes'] is not None:
        estimate += f" (per-PR budget {result['budget_minutes']} min)"
    lines.append(estimate)
    return '\n'.join(lines)


def placeholder(value):
    return not isinstance(value, str) or not value.strip() or value.strip().startswith('<')


def audit(files, config):
    """Check the map against the repository's tracked files. Returns [(level, message)] with FAIL, WARN or PASS."""
    items = []
    features, defs, targets = config.get('features', {}), config.get('suites', {}), config.get('targets', {})
    result = plan(files, config)
    unmapped = result['unmapped']
    if unmapped:
        items.append(('FAIL', f'{len(unmapped)} tracked file(s) match no feature or static pattern, so changing them '
                              f'would verify every feature: {", ".join(unmapped[:8])}. Add them to a feature\'s '
                              'paths or to static (references/mapping.md)'))
    else:
        items.append(('PASS', f'Every tracked file maps to a feature, the gate or static ({len(features)} features)'))
    empty = [fid for fid, f in features.items() if not any(matches(p, f['paths']) for p in files)]
    if empty:
        items.append(('FAIL', f'Feature(s) {", ".join(empty)} match no tracked file; the code moved or was removed. '
                              'Update their paths or delete them'))
    dead = sorted({pat for f in features.values() for pat in f['paths'] if not any(matches(p, [pat]) for p in files)}
                  - {pat for fid in empty for pat in features[fid]['paths']})
    if dead:
        items.append(('WARN', f'Path pattern(s) match no tracked file: {", ".join(dead[:8])}'))
    code = [p for p in files if not matches(p, GATE_PATHS) and not matches(p, config.get('static', []))]
    for fid, f in features.items():
        hit = sum(1 for p in code if matches(p, f['paths']))
        own = set(f.get('suites', [])) - set(config.get('always_suites', []))
        if own and len(code) >= 20 and hit > len(code) / 2 and len(features) > 1:
            items.append(('WARN', f'Feature {fid} covers {hit} of {len(code)} code files, so most changes run its '
                                  f'suites ({", ".join(sorted(own))}). Narrow its paths and map shared code separately'))
    named = set(config.get('always_suites', [])) | set(config.get('static_suites', [])) | \
        set(config.get('full_suites', [])) | {s for f in features.values() for s in f.get('suites', [])}
    undefined = sorted(named - set(defs))
    if undefined:
        items.append(('FAIL', f'Suite(s) {", ".join(undefined)} are used but not defined under "suites" with the '
                              'command that runs them and their measured minutes'))
    norun = sorted(s for s in named & set(defs) if placeholder(defs[s].get('run')))
    if norun:
        items.append(('WARN', f'Suite(s) {", ".join(norun)} have no "run" command, so `verify_plan.py ci` cannot run them'))
    untimed = sorted(s for s in named & set(defs) if minutes_of(config, s) is None)
    if untimed:
        items.append(('WARN', f'No measured "minutes" for suite(s) {", ".join(untimed)}; time each one so plans '
                              'show what a PR costs'))
    for name, target in targets.items():
        if placeholder(target.get('ready')) or (placeholder(target.get('start')) and placeholder(target.get('url'))):
            items.append(('FAIL', f'Target {name} needs "ready" (a URL that answers once the app is up) and either '
                                  '"start" (a command) or "url" (a deployed app)'))
        if placeholder(target.get('auth')):
            items.append(('WARN', f'Target {name} does not say how verification signs in ("auth"); write "none" '
                                  'if the app has no sign-in'))
    missing = sorted({d['target'] for d in defs.values() if d.get('target') and d['target'] not in targets})
    if missing:
        items.append(('FAIL', f'Suite target(s) {", ".join(missing)} are not defined under "targets"'))
    # Journeys against a running app never run on every PR; each belongs to the features it checks.
    for key in ('always_suites', 'static_suites'):
        journeys = sorted(s for s in config.get(key, []) if defs.get(s, {}).get('target'))
        if journeys:
            items.append(('FAIL', f'{key} include journey suite(s) {", ".join(journeys)}, so every PR would drive the '
                                  'app; attach them to the features they check'))
    budget = config.get('pr_budget_minutes')
    if not isinstance(budget, (int, float)) or isinstance(budget, bool):
        if not untimed and not undefined:
            items.append(('PASS', 'No journey suite runs on every PR; no per-PR time limit is set'))
        return items
    always = set(config.get('always_suites', []))
    every = max(cost(always, config)[0], cost(always | set(config.get('static_suites', [])), config)[0])
    gate = cost(always | set(config.get('full_suites', [])), config)[0]
    if every > budget:
        items.append(('FAIL', f'Suites that run on every PR take {every} min, over the {budget} min budget; keep '
                              'slow suites such as browser journeys out of always_suites and static_suites'))
    if gate > budget:
        items.append(('FAIL', f'A gate change runs always_suites and full_suites for {gate} min, over the {budget} min '
                              'budget; full_suites are for fast whole-repository checks, not journeys'))
    over = []
    seen = set()
    for path in code:
        hit = frozenset(fid for fid, f in features.items() if matches(path, f['paths']))
        if not hit or hit in seen:
            continue
        seen.add(hit)
        suites = always | {s for fid in hit for s in features[fid].get('suites', [])}
        limit = max(features[fid].get('budget_minutes', budget) for fid in hit)
        minutes = max(cost(b, config)[0] for b in binpack(suites, config, shard_count(config)))
        if minutes > limit:
            over.append(f'{path} -> {", ".join(sorted(hit))} ({minutes} min)')
    if over:
        items.append(('WARN', f'These changes exceed the {budget} min per-PR budget: {"; ".join(over[:6])}. Split '
                              'slow suites so a feature runs only its own journeys, or record the owner\'s '
                              '"budget_minutes" for that feature'))
    elif every <= budget and gate <= budget and not untimed and not undefined:
        items.append(('PASS', f'Every single-area change fits the {budget} min budget; checks on every PR take '
                              f'{every} min'))
    return items


def inventory(files, config, depth=2):
    """Group tracked files by directory and show how each group is mapped, as the starting point for mapping."""
    groups = {}
    for path in files:
        parts = path.split('/')
        key = '/'.join(parts[:min(depth, len(parts) - 1)]) or '.'
        group = groups.setdefault(key, {'files': 0, 'features': set(), 'static': 0, 'gate': 0, 'unmapped': 0})
        group['files'] += 1
        hit = {fid for fid, f in config.get('features', {}).items() if matches(path, f['paths'])}
        group['features'] |= hit
        if matches(path, GATE_PATHS):
            group['gate'] += 1
        elif not hit and matches(path, config.get('static', [])):
            group['static'] += 1
        elif not hit:
            group['unmapped'] += 1
    return groups


def tracked_files(root='.'):
    return [line for line in run('git', '-C', str(root), 'ls-files').splitlines() if line]


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def expand(text, env):
    return re.sub(r'\$\{?(PORT|BASE_URL)\}?', lambda m: env.get(m.group(1), m.group(0)), text or '')


def probe_url(url):
    """Return (ok, detail) for one request to a readiness URL."""
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return 200 <= response.status < 400, f'HTTP {response.status}'
    except urllib.error.HTTPError as error:
        hint = ' (the app is protected: give verification a bypass token or test account)' \
            if error.code in (401, 403) else ''
        return False, f'HTTP {error.code}{hint}'
    except (urllib.error.URLError, OSError) as error:
        return False, str(getattr(error, 'reason', error))


@contextmanager
def started(name, target, timeout, url=None, log=None, extra=None):
    """Start a target (or use its deployed URL), wait until its ready URL answers, and stop it afterwards."""
    port = str(free_port())
    env = {**os.environ, **(extra or {}), 'PORT': port}
    env['BASE_URL'] = url or expand(target.get('url') or f'http://127.0.0.1:{port}', env)
    ready = url or expand(target['ready'], env)
    proc = None
    if not url and not placeholder(target.get('start')):
        out = open(log, 'w') if log else subprocess.DEVNULL
        proc = subprocess.Popen(expand(target['start'], env), shell=True, env=env, stdout=out,
                                stderr=subprocess.STDOUT, start_new_session=True)
    try:
        deadline, detail = time.monotonic() + timeout, 'not tried'
        while True:
            if proc and proc.poll() is not None:
                raise Refused(f'Target {name}: start command exited with {proc.returncode} before {ready} answered'
                              + (f'; see {log}' if log else ''))
            ok, detail = probe_url(ready)
            if ok:
                break
            if time.monotonic() > deadline:
                raise Refused(f'Target {name}: {ready} did not answer within {timeout}s ({detail})'
                              + (f'; see {log}' if log else ''))
            time.sleep(1)
        yield env
    finally:
        if proc:
            stop_group(proc)


def stop_group(proc, grace=10):
    """Stop the target's whole process group and wait for every member to exit, not just the shell that
    started it (dash does not exec its last command), so coverage and logs are fully written."""
    def alive():
        try:
            os.killpg(proc.pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline:
        proc.poll()
        if not alive():
            return
        time.sleep(0.1)
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    proc.wait()


def shell(command, env=None):
    started_at = time.monotonic()
    code = subprocess.run(command, shell=True, env=env).returncode
    return code, round((time.monotonic() - started_at) / 60, 1)


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


OBJECTIVE_HEADING = re.compile(r'^ {0,3}#{1,6}[ \t]+objective\b', re.I)
OBJECTIVE_LINE = re.compile(r'^ {0,3}\**objective\**[ \t]*:[ \t]*(.*)$', re.I)
FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})')
HEADING = re.compile(r'^ {0,3}#{1,6}(?:[ \t]|$)')


def visible_lines(body):
    """Lines GitHub shows as prose: code fences, indented code and HTML comments are dropped.

    Follows CommonMark: a fence closes only with the same character at least as long as the opener,
    and an unclosed fence or comment hides the rest of the document.
    """
    lines, fence, comment = [], None, False
    for line in (body or '').splitlines():
        if comment:
            if '-->' in line:
                comment = False
                line = line.split('-->', 1)[1]
            else:
                continue
        if fence:
            closing = FENCE.match(line)
            if closing and closing.group(1)[0] == fence[0] and len(closing.group(1)) >= len(fence) \
                    and not line.strip().lstrip(fence[0]):
                fence = None
            continue
        opening = FENCE.match(line)
        if opening:
            fence = opening.group(1)
            continue
        if line.startswith('    ') or line.startswith('\t'):
            continue  # indented code block
        while '<!--' in line:
            before, rest = line.split('<!--', 1)
            if '-->' in rest:
                line = before + rest.split('-->', 1)[1]
            else:
                line, comment = before, True
        lines.append(line)
    return lines


def states_objective(body):
    """The description must open with the objective: its first non-empty line is an `Objective` heading or an
    `Objective:` line, and that line or its section has at least 10 characters of content. Top-level code fences
    and HTML comments don't count toward the content. This is a presence check against a forgotten objective;
    whether the content is a good objective is for the agent and the verifier to judge."""
    raw = [line for line in (body or '').splitlines() if line.strip()]
    if not raw or not (OBJECTIVE_HEADING.match(raw[0]) or OBJECTIVE_LINE.match(raw[0])):
        return False
    lines = visible_lines(body)
    first = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first is None or lines[first] != raw[0]:
        return False
    match = OBJECTIVE_LINE.match(lines[first])
    if match:
        text = match.group(1)
    else:
        section = []
        for following in lines[first + 1:]:
            if HEADING.match(following):
                break
            section.append(following)
        text = ' '.join(section)
    return len(re.sub(r'\s+', ' ', text).strip()) >= 10


def evaluate(pr, config):
    """Return (state, description) for the jfactory verified status at the PR head."""
    result = plan(pr['files'], config)
    if result['level'] != 'static' and config.get('require_objective', True) and not states_objective(pr.get('body')):
        return 'failure', 'PR description must start with its objective: an Objective heading (such as "## Objective") or "Objective:" line'
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
    result = plan(files, config, load_impact(args.impact) if args.impact else None)
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


def cmd_audit(args):
    config = load_config(args.config_ref)
    items = audit(tracked_files(), config)
    for level, text in items:
        print(f'{level}: {text}')
    return 1 if any(level == 'FAIL' for level, _ in items) else 0


def cmd_inventory(args):
    config = load_config(root='.') if Path(CONFIG).is_file() else {'features': {}}
    groups = inventory(tracked_files(), config, args.depth)
    print(f"{'directory':40} {'files':>5}  mapped to")
    for key in sorted(groups):
        g = groups[key]
        where = ', '.join(sorted(g['features']))
        extra = [f'{g[k]} {k}' for k in ('static', 'gate', 'unmapped') if g[k]]
        print(f"{key:40} {g['files']:>5}  {where or '-'}" + (f"  ({', '.join(extra)})" if extra else ''))


def cmd_ci(args):
    """Run the suites a change needs (or every suite with --all), after checking the map is complete."""
    config = load_config(root='.')
    problems = [text for level, text in audit(tracked_files(), config) if level == 'FAIL']
    for text in problems:
        print(f'FAIL: {text}')
    if problems:
        return 1
    defs, targets = config.get('suites', {}), config.get('targets', {})
    if args.suites:
        suites = args.suites
    elif args.all:
        suites = sorted(defs)
    else:
        impact = load_impact(args.impact) if args.impact else None
        if args.impact and not impact:
            print(f'No recorded coverage at {args.impact}; planning from the map only')
        result = plan(git_files(args.base), config, impact)
        print(render_plan(result) + '\n')
        suites = result['suites']
    if args.shard:
        index, count = args.shard
        suites = binpack(suites, config, count)[index - 1]
        print(f"Shard {index}/{count}: {', '.join(suites) or 'nothing to run'}")
    record = tempfile.mkdtemp(prefix='jfactory-coverage-') if args.impact_out else None
    tracked = set(tracked_files()) if record else set()
    executed = {}
    failed, report = [], []
    for suite in suites:
        definition = defs.get(suite, {})
        if placeholder(definition.get('run')):
            failed.append(suite)
            report.append(f'{suite}: no "run" command in {CONFIG}')
            continue
        extra = {}
        if record:
            # The suite (and its target) write coverage here; Node processes do so automatically.
            folder = Path(record) / re.sub(r'[^\w.-]', '_', suite)
            folder.mkdir()
            extra = {'JFACTORY_COVERAGE_DIR': str(folder), 'NODE_V8_COVERAGE': str(folder)}
        print(f'::group::{suite}: {definition["run"]}', flush=True)
        try:
            if definition.get('target'):
                name = definition['target']
                with started(name, targets[name], args.timeout, extra=extra) as env:
                    code, minutes = shell(expand(definition['run'], env), env)
            else:
                code, minutes = shell(definition['run'], {**os.environ, **extra})
        except Refused as error:
            code, minutes = 1, 0
            print(error)
        print('::endgroup::', flush=True)
        if record:
            files = set()
            for report_file in Path(extra['JFACTORY_COVERAGE_DIR']).rglob('*'):
                if report_file.is_file():
                    files |= coverage_files(report_file, '.')
            executed[suite] = sorted(files & tracked)
        expected = minutes_of(config, suite)
        note = f' (recorded {expected} min; update "minutes")' if expected and minutes > expected * 1.5 + 1 else ''
        report.append(f"{suite}: {'passed' if code == 0 else f'failed ({code})'} in {minutes} min{note}")
        if code:
            failed.append(suite)
    print('\n'.join(report) or 'No suites to run')
    if record:
        head = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
        Path(args.impact_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.impact_out).write_text(json.dumps(
            {'version': 1, 'commit': head, 'at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
             'suites': {k: v for k, v in executed.items() if v}}, indent=1) + '\n')
        empty = sorted(k for k, v in executed.items() if not v)
        print(f'Recorded coverage for {len(executed) - len(empty)} suite(s) in {args.impact_out}'
              + (f"; no coverage from {', '.join(empty)} (see references/mapping.md)" if empty else ''))
    return 1 if failed else 0


def cmd_smoke(args):
    """Prove a target starts and answers where verification runs, and optionally record a receipt."""
    config = load_config(root='.')
    target = config.get('targets', {}).get(args.target)
    if target is None:
        raise Refused(f'No target {args.target!r} in {CONFIG}; add it under "targets"')
    steps, ok = [], True

    def step(name, command, env=None):
        nonlocal ok
        if not ok or placeholder(command):
            return
        code, minutes = shell(expand(command, env or os.environ), env)
        steps.append({'step': name, 'ok': code == 0, 'minutes': minutes,
                      'detail': f'`{command}` exited {code}'})
        ok = code == 0

    if not args.no_setup:
        step('setup', target.get('setup'))
    step('doctor', target.get('doctor'))
    if ok:
        log = str(Path(tempfile.gettempdir()) / f'jfactory-{args.target}-{os.getpid()}.log')
        try:
            with started(args.target, target, args.timeout, url=args.url, log=log) as env:
                steps.append({'step': 'ready', 'ok': True, 'detail': f"{env['BASE_URL']} answered"})
                step('probe', target.get('probe'), env)
        except Refused as error:
            steps.append({'step': 'ready', 'ok': False, 'detail': str(error)})
            ok = False
    for item in steps:
        print(f"{'PASS' if item['ok'] else 'FAIL'}: {item['step']}: {item['detail']}")
    if args.record:
        path = Path(args.record)
        data = json.loads(path.read_text()) if path.is_file() else {}
        head = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
        data[args.target] = {'ok': ok, 'commit': head, 'host': platform.node(), 'fresh': args.fresh,
                             'at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'steps': steps}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=1) + '\n')
    print(f"Target {args.target} {'is ready' if ok else 'is not ready; fix the failed step before verifying'}")
    return 0 if ok else 1


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


def shard_arg(value):
    match = re.fullmatch(r'(\d+)/(\d+)', value)
    if not match or not 1 <= int(match.group(1)) <= int(match.group(2)):
        raise argparse.ArgumentTypeError('use I/N, for example 2/4')
    return int(match.group(1)), int(match.group(2))


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
    p.add_argument('--impact', help='Recorded coverage (file or directory) that adds suites executing changed files')
    p.set_defaults(func=cmd_plan)
    p = sub.add_parser('audit', help='Check the map covers every tracked file, defines its suites and fits the budget')
    p.set_defaults(func=cmd_audit)
    p = sub.add_parser('inventory', help='Show tracked files by directory and how each is mapped')
    p.add_argument('--depth', type=int, default=2)
    p.set_defaults(func=cmd_inventory)
    p = sub.add_parser('ci', help='Run the suites this change needs, after checking the map')
    p.add_argument('--base', default='origin/main')
    p.add_argument('--all', action='store_true', help='Run every defined suite, for scheduled or pre-release runs')
    p.add_argument('--suites', type=listing, help='Run only these suites, for example to time one')
    p.add_argument('--timeout', type=int, default=300, help='Seconds to wait for a target to answer')
    p.add_argument('--shard', type=shard_arg, help='Run group I of N (I/N), balanced by recorded minutes')
    p.add_argument('--impact', help='Recorded coverage (file or directory) that adds suites executing changed files')
    p.add_argument('--impact-out', help='Record which tracked files each suite executed, for later --impact')
    p.set_defaults(func=cmd_ci)
    p = sub.add_parser('smoke', help='Prove a target starts and answers where verification runs')
    p.add_argument('--target', required=True)
    p.add_argument('--no-setup', action='store_true', help='Skip the setup command (dependencies already installed)')
    p.add_argument('--url', help='Use this deployed URL, such as the PR preview, instead of starting the app')
    p.add_argument('--timeout', type=int, default=300)
    p.add_argument('--record', help='Write a receipt, for example .jfactory/smoke.json')
    p.add_argument('--fresh', action='store_true', help='Record that this ran in a new workspace or runner')
    p.set_defaults(func=cmd_smoke)
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
        if args.command in ('check', 'verdict') and not args.repo:
            args.repo = run('gh', 'repo', 'view', '--json', 'nameWithOwner', '--jq', '.nameWithOwner').strip()
        return args.func(args) or 0
    except Refused as error:
        print(f'REFUSED: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
