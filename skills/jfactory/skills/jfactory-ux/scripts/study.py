#!/usr/bin/env python3
"""Private UX study folders, named Playwright CLI sessions and local walkthroughs."""
import argparse
import hashlib
from datetime import datetime, timezone
from html import escape
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
from urllib.parse import quote, unquote, urlsplit
import uuid

CLI_PACKAGE = '@playwright/cli@0.1.21'


def cli_environment(folder):
    """Isolate the pinned CLI's browser registry and dashboard singleton per study."""
    env = os.environ.copy()
    env.pop('PLAYWRIGHT_CLI_SESSION', None)
    # These are internal Playwright hooks. Browser/dashboard smoke tests cover
    # them against CLI_PACKAGE; revalidate when updating the pinned dependency.
    registry = folder / '.browser-control'
    tag = hashlib.sha256(str(folder).encode()).hexdigest()[:16]
    # Unix socket paths must stay short even for deeply nested study folders.
    sockets = Path('/tmp') / f'jfactory-ux-{os.getuid()}-{tag}'
    for directory in (registry, sockets):
        if directory.is_symlink():
            raise ValueError('Browser control directories must not be symlinks')
        directory.mkdir(mode=0o700, exist_ok=True)
        if directory.stat().st_uid != os.getuid():
            raise ValueError('Browser control directory belongs to another user')
        directory.chmod(0o700)
    env['PWTEST_DAEMON_SESSION_DIR'] = str(registry)
    env['PWTEST_SERVER_REGISTRY'] = str(registry / 'browsers')
    env['PWTEST_SOCKETS_DIR'] = str(sockets)
    return env


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def init(project, name, url, objective):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,47}', name):
        raise ValueError('Study name must be 1-48 lowercase letters, digits or hyphens')
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Use an http(s) app URL without credentials')
    project = Path(project).resolve()
    if not project.is_dir():
        raise ValueError('Project must be an existing directory')
    root = project / '.context' / 'ux'
    for path in (root.parent, root, root / name):
        if path.is_symlink():
            raise ValueError('Study directories must not be symlinks')
    root.mkdir(parents=True, exist_ok=True)
    # Also protect studies in projects that do not already ignore .context/.
    ignore = root / '.gitignore'
    if ignore.is_symlink():
        raise ValueError('Study ignore file must not be a symlink')
    if not ignore.exists():
        ignore.write_text('*\n')
    elif ignore.read_text().strip() != '*':
        raise ValueError('Study directory needs a .gitignore containing only *')
    folder = root / name
    folder.mkdir(mode=0o700)  # Refuse an existing study instead of replacing its evidence.
    (folder / 'artifacts').mkdir(mode=0o700)
    write_json(folder / 'study.json', {
        'created': datetime.now(timezone.utc).isoformat(), 'url': url,
        'objective': objective, 'session': 'jux-' + uuid.uuid4().hex[:12],
        'approved_destinations': [f'{parsed.scheme}://{parsed.netloc}'],
        'approved_actions': ['Observe and navigate; no data mutations'],
        'account_context': 'Not established',
    })
    write_json(folder / 'browser.json', {
        'browser': {'browserName': 'chromium', 'launchOptions': {'channel': 'chrome'},
                    'contextOptions': {'viewport': {'width': 1440, 'height': 900}}},
        'outputDir': str(folder / 'artifacts'), 'outputMode': 'file',
    })
    write_json(folder / 'report.json', {
        'summary': '', 'context': '', 'app_map': '',
        'journeys': [], 'findings': [], 'unknowns': ['Study has not been conducted'],
    })
    return folder


def browser(folder, args):
    folder = Path(folder).resolve()
    study = json.loads((folder / 'study.json').read_text())
    if not args or args[0] in ('kill-all', 'close-all', 'attach', 'install'):
        raise ValueError('Use a command for this study only; no global cleanup or external attachment')
    if any(a.startswith(('-s', '--session', '--config', '--profile', '--persistent')) for a in args[1:]):
        raise ValueError('The helper owns the session, profile and config; edit browser.json if needed')
    if args[0].startswith('-') and args[0] not in ('--help', '--version'):
        raise ValueError('Start with a browser command, --help or --version')
    command = ['npx', '--yes', CLI_PACKAGE, '-s=' + study['session'], *args]
    if args[0] == 'open':
        command += ['--config=' + str(folder / 'browser.json'), '--profile=' + str(folder / 'profile')]
    # No shell parsing. Relative captures/scripts resolve inside the private study.
    # This is a convenience wrapper, not a restriction on browser actions or URLs.
    return subprocess.run(command, cwd=folder, env=cli_environment(folder)).returncode


def capture_directory(folder):
    for directory in (folder / 'artifacts', folder / 'artifacts' / 'steps'):
        if directory.is_symlink():
            raise ValueError('Study capture directories must not be symlinks')
    return folder / 'artifacts' / 'steps'


def step(folder, args, run=None):
    """Perform one browser action, then capture what the user now sees. Every action gets a screenshot, so a
    walkthrough can't skip the moments between the states someone chose to capture."""
    run = run or browser
    folder = Path(folder).resolve()
    if not args or args[0] in ('screenshot', 'video-start', 'video-stop', 'tracing-start', 'tracing-stop', 'close'):
        raise ValueError('step takes one user action (open, click, fill, type, press, select, resize, ...)')
    log_path = folder / 'steps.json'
    steps = json.loads(log_path.read_text()) if log_path.exists() else []
    number = len(steps) + 1
    capture_directory(folder).mkdir(mode=0o700, exist_ok=True)
    shot = f'artifacts/steps/{number:03d}.png'
    if (folder / shot).is_symlink() or ((folder / shot).exists() and not (folder / shot).is_file()):
        raise ValueError(f'{shot} must be absent or a regular file, not a link or directory')
    started = datetime.now(timezone.utc)
    entry = {'step': number, 'action': ' '.join(args), 'exit': None, 'seconds': None, 'at': started.isoformat(),
             'screenshot': None, 'note': ''}
    try:
        entry['exit'] = run(folder, list(args))
    finally:
        # Record the action before anything else can fail: it happened, and the trail must not hide it. The
        # screenshot stays null, which blocks rendering, until the capture below is published.
        entry['seconds'] = round((datetime.now(timezone.utc) - started).total_seconds(), 2)
        steps.append(entry)
        write_json(log_path, steps)
    # Capture to a fresh name, then rename over the leaf, so nothing is written through a planted link.
    fresh = folder / f'artifacts/steps/{number:03d}-{uuid.uuid4().hex}.png'
    try:
        captured = run(folder, ['screenshot', f'--filename={fresh.relative_to(folder)}'])
        if captured or not fresh.is_file() or fresh.is_symlink():
            raise ValueError('the screenshot command failed')
        os.replace(fresh, folder / shot)
    except Exception as error:
        try:
            if fresh.is_symlink() or fresh.is_file():
                fresh.unlink()
        except OSError:
            pass
        raise ValueError(f'Step {number} ran, but its screenshot was not captured ({error}); the trail will not '
                         'render until the session is fixed and the journey is walked again') from error
    entry['screenshot'] = shot
    write_json(log_path, steps)
    return number, shot


def note(folder, number, text):
    """Record what the reviewer saw in a step's screenshot, after looking at it."""
    folder = Path(folder).resolve()
    steps = json.loads((folder / 'steps.json').read_text())
    if not text.strip():
        raise ValueError('A note says what the screenshot shows: layout, text, state and anything wrong')
    match = [s for s in steps if s['step'] == number]
    if not match:
        raise ValueError(f'No step {number}')
    match[0]['note'] = text.strip()
    write_json(folder / 'steps.json', steps)


def walkthrough(folder):
    """Render the step-by-step trail. Refuses while any step's screenshot has no note, because the point is that
    someone looked at every step."""
    folder = Path(folder).resolve()
    steps = json.loads((folder / 'steps.json').read_text()) if (folder / 'steps.json').exists() else []
    if not steps:
        raise ValueError('No steps recorded; drive the journey with `study.py step`')
    shots = capture_directory(folder)
    missing = []
    for s in steps:
        path, linked = folder, False
        for part in Path(s.get('screenshot') or '').parts:
            path = path / part
            linked = linked or path.is_symlink()
        if not s.get('screenshot') or linked or not path.resolve().is_relative_to(shots) or not path.is_file():
            missing.append(str(s['step']))
    if missing:
        raise ValueError('Step(s) ' + ', '.join(missing) + ' have no screenshot inside artifacts/steps; walk the journey '
                         'again in a working session')
    unseen = [str(s['step']) for s in steps if not str(s.get('note') or '').strip()]
    if unseen:
        raise ValueError('Look at each screenshot and note what it shows first; no note for step(s) ' + ', '.join(unseen))
    study = json.loads((folder / 'study.json').read_text())
    rows = []
    for s in steps:
        href = quote(s['screenshot'], safe='/')
        rows.append(f'<li><p><strong>{escape(s["action"])}</strong> · {s["seconds"]}s'
                    + (f' · exit {s["exit"]}' if s['exit'] else '') + f'</p><p>{escape(s["note"])}</p>'
                    f'<figure><img loading="lazy" src="{href}" alt="Step {s["step"]}"></figure></li>')
    doc = ('<!doctype html><html lang="en"><meta charset="utf-8">'
           '<meta name="viewport" content="width=device-width, initial-scale=1">'
           '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src \'self\'; style-src \'unsafe-inline\'">'
           '<title>Step-by-step walkthrough</title><style>body{font:16px/1.5 system-ui,sans-serif;max-width:1040px;'
           'margin:auto;padding:32px 20px;color:#192230}li{margin-bottom:28px}img{width:100%;border:1px solid #dde1e7;'
           'border-radius:8px}</style><h1>' + escape(study['objective']) + '</h1><p>Every action, with what the reviewer saw '
           'after it.</p><ol>' + ''.join(rows) + '</ol></html>')
    out = folder / 'steps.html'
    out.write_text(doc)
    md = ['# Step-by-step walkthrough: ' + study['objective'], '']
    md += [f"{s['step']}. **{s['action']}** ({s['seconds']}s): {s['note']} [`{s['screenshot']}`]" for s in steps]
    (folder / 'steps.md').write_text('\n'.join(md) + '\n')
    return out


POSTURES = ('first-time', 'numbers', 'edge-input', 'state', 'errors', 'other')
BUCKETS = {'artifact': 'the explorer misread the app (a new-tab link, lazy content, text split around a link)',
           'environment': 'only the local stack lacks a key, service or limit',
           'design': 'the code, its tests or its copy say the behavior is intended',
           'fixture': 'the seed data lacks something real records have',
           'not-reproduced': 'the repro test passed, so the bug did not reproduce',
           'duplicate': 'another finding describes the same defect'}
SEVERITY = {5: 'critical', 4: 'high', 3: 'medium', 2: 'low', 1: 'trivial'}


def ledger(folder):
    folder = Path(folder).resolve()
    if not (folder / 'study.json').is_file():
        raise ValueError(f'No study at {folder}; create it with `study.py init`')
    path = folder / 'bugs.json'
    return folder, path, (json.loads(path.read_text()) if path.exists() else {'charters': [], 'findings': []})


def charter(folder, slug, posture, goal):
    """Record one bug-bash charter: one area, one posture, one sentence naming where it starts."""
    folder, path, data = ledger(folder)
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,47}', slug):
        raise ValueError('Charter slug must be 1-48 lowercase letters, digits or hyphens')
    if any(c['slug'] == slug for c in data['charters']):
        raise ValueError(f'Charter {slug} already exists')
    if posture not in POSTURES:
        raise ValueError('Posture must be one of ' + ', '.join(POSTURES))
    if len(goal.split()) < 5:
        raise ValueError('A charter is one sentence naming the start route, the area and what to check')
    data['charters'].append({'slug': slug, 'posture': posture, 'goal': goal.strip(),
                             'at': datetime.now(timezone.utc).isoformat()})
    write_json(path, data)


def claim(folder, charter_slug, kind, severity, title, where, expected, actual, steps, evidence):
    """Record what an explorer reported. A claim is a model's hypothesis until a repro test confirms it."""
    folder, path, data = ledger(folder)
    if charter_slug not in {c['slug'] for c in data['charters']}:
        raise ValueError(f'No charter {charter_slug}; record it with `study.py charter` first')
    if kind not in ('issue', 'warning') or severity not in SEVERITY:
        raise ValueError('Kind is issue or warning, severity 1 (trivial) to 5 (critical)')
    for field, value in (('title', title), ('where', where), ('expected', expected), ('actual', actual)):
        if not value.strip():
            raise ValueError(f'A finding needs {field}')
    if not steps:
        raise ValueError('A finding needs reproduction steps (--step, repeated)')
    for name in evidence:
        target = (folder / name).resolve()
        if not target.is_relative_to(folder / 'artifacts') or not target.is_file():
            raise ValueError('Evidence must be an existing file inside artifacts/: ' + name)
    number = len(data['findings']) + 1
    data['findings'].append({'id': number, 'charter': charter_slug, 'kind': kind, 'severity': severity,
                             'title': title.strip(), 'where': where.strip(), 'expected': expected.strip(),
                             'actual': actual.strip(), 'steps': [x.strip() for x in steps], 'evidence': evidence,
                             'status': 'claimed', 'at': datetime.now(timezone.utc).isoformat()})
    write_json(path, data)
    return number


def finding(data, number):
    match = [f for f in data['findings'] if f['id'] == number]
    if not match:
        raise ValueError(f'No finding {number}')
    if match[0]['status'] != 'claimed':
        raise ValueError(f"Finding {number} is already {match[0]['status']}")
    return match[0]


def reject(folder, number, bucket, reason):
    """Close a claim that is not a product bug, naming the check that settled it."""
    folder, path, data = ledger(folder)
    item = finding(data, number)
    if bucket not in BUCKETS:
        raise ValueError('Bucket must be one of ' + ', '.join(BUCKETS))
    if len(reason.split()) < 3:
        raise ValueError('Say what settled it: the check you ran, the file and line, or the finding it duplicates')
    item.update(status='rejected', bucket=bucket, reason=reason.strip(), closed=datetime.now(timezone.utc).isoformat())
    write_json(path, data)


def confirm(folder, number, repro, expect_failure, command, timeout=300):
    """Confirm a claim only when its repro test fails today, for the reason the finding reports. A pass means the
    bug did not reproduce; any other failure means the test is wrong."""
    folder, path, data = ledger(folder)
    item = finding(data, number)
    project = folder.parents[2]
    test = (project / repro).resolve()
    if not test.is_relative_to(project) or not test.is_file():
        raise ValueError(f'Repro test {repro} must be a file in the project')
    try:
        pattern = re.compile(expect_failure)
    except re.error as error:
        raise ValueError(f'--expect-failure is not a valid regular expression: {error}')
    if not command:
        raise ValueError('Give the command that runs the repro test after --')
    logs = folder / 'artifacts' / 'bugs'
    if logs.is_symlink():
        raise ValueError('artifacts/bugs must not be a symlink')
    logs.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        # Its own process group, so an app the test runner started is stopped with it.
        process = subprocess.Popen(command, cwd=project, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   start_new_session=True)
    except OSError as error:
        raise ValueError(f'The repro command could not start: {error}')
    try:
        output, _ = process.communicate(timeout=timeout)
        code = process.returncode
    except subprocess.TimeoutExpired:
        code = None
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if code is None:
        output, _ = process.communicate()
    log = logs / f'{number:03d}.log'
    log.write_bytes(output)
    text = output.decode(errors='replace')
    if code is None:
        raise ValueError(f'The repro timed out after {timeout}s; a timeout proves nothing. Fix the test ({log})')
    if code == 0:
        raise ValueError('The repro test passed, so the bug did not reproduce. Reject the finding with --bucket '
                         'not-reproduced, and keep the test as a regression test only if it is worth having')
    if not pattern.search(text):
        raise ValueError(f'The repro failed, but not with {expect_failure!r}: the test is wrong (a locator, a timeout, '
                         f'a setup error), not proof of the bug. Fix it and confirm again ({log})')
    revision = subprocess.run(['git', '-C', str(project), 'rev-parse', 'HEAD'], capture_output=True, text=True)
    item.update(status='confirmed', repro=str(test.relative_to(project)), command=command,
                expect_failure=expect_failure, log=str(log.relative_to(folder)),
                log_sha256=hashlib.sha256(output).hexdigest(), revision=revision.stdout.strip() or None,
                closed=datetime.now(timezone.utc).isoformat())
    write_json(path, data)
    return log


def bugs(folder):
    """Write the bug-bash report: confirmed bugs first, then unverified claims, rejections and charters."""
    folder, path, data = ledger(folder)
    if not data['charters']:
        raise ValueError('No charters recorded; plan them with `study.py charter`')
    found = data['findings']
    order = lambda f: (-f['severity'], f['id'])  # noqa: E731
    confirmed = sorted((f for f in found if f['status'] == 'confirmed' and f['kind'] == 'issue'), key=order)
    open_claims = sorted((f for f in found if f['status'] == 'claimed'), key=order)
    rejected = [f for f in found if f['status'] == 'rejected']
    warnings = sorted((f for f in found if f['status'] == 'confirmed' and f['kind'] == 'warning'), key=order)
    md = ['# Bug bash: ' + json.loads((folder / 'study.json').read_text())['objective'], '',
          f'{len(confirmed)} confirmed, {len(open_claims)} unverified, {len(rejected)} rejected, '
          f'{len(data["charters"])} charters.', '', '## Confirmed bugs', '']
    for f in confirmed:
        md += [f"### {f['id']}. {f['title']} ({SEVERITY[f['severity']]})", '',
               f"- **Where:** {f['where']}", f"- **Expected:** {f['expected']}", f"- **Actual:** {f['actual']}",
               '- **Steps:** ' + ' → '.join(f['steps']),
               f"- **Repro test:** `{f['repro']}` fails with `{f['expect_failure']}` at `{(f.get('revision') or '?')[:12]}` "
               f"([log]({f['log']}))",
               '- **Evidence:** ' + (', '.join(f'[{e}]({e})' for e in f['evidence']) or 'none'),
               f"- **Charter:** {f['charter']}", '']
    if not confirmed:
        md += ['None.', '']
    md += ['## Unverified claims (not bugs until a repro test confirms them)', '']
    md += [f"- {f['id']}. {f['title']} ({SEVERITY[f['severity']]} {f['kind']}, {f['where']})" for f in open_claims] or ['None.']
    md += ['', '## Rejected', '']
    for bucket in BUCKETS:
        items = [f for f in rejected if f['bucket'] == bucket]
        if items:
            md += [f'**{bucket}** ({BUCKETS[bucket]}):'] + [f"- {f['id']}. {f['title']}: {f['reason']}" for f in items] + ['']
    if not rejected:
        md += ['None.', '']
    if warnings:
        md += ['## Confirmed warnings', ''] + [f"- {f['id']}. {f['title']} ({f['where']})" for f in warnings] + ['']
    md += ['## Charters', ''] + [f"- `{c['slug']}` ({c['posture']}): {c['goal']}" for c in data['charters']]
    out = folder / 'bugs.md'
    out.write_text('\n'.join(md) + '\n')
    return out, len(open_claims)


def render(folder):
    folder = Path(folder).resolve()
    report = json.loads((folder / 'report.json').read_text())
    study = json.loads((folder / 'study.json').read_text())
    for field in ('summary', 'context', 'app_map'):
        if not isinstance(report.get(field), str) or not report[field].strip():
            raise ValueError('Fill report.' + field + ' from observations before rendering')
    if not report.get('journeys'):
        raise ValueError('Record journey coverage, including blocked journeys')

    def text(value):
        if not isinstance(value, str):
            raise ValueError('Report text fields must be strings')
        return escape(value)

    def evidence(files):
        result = []
        for name in files:
            path = (folder / name).resolve()
            if not path.is_relative_to(folder / 'artifacts') or not path.is_file():
                raise ValueError('Evidence must be an existing file inside artifacts/: ' + name)
            # Do not embed SVG/HTML/scripts from an untrusted application.
            href = quote(path.relative_to(folder).as_posix(), safe='/')
            caption = text(name)
            media = ''
            if path.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp'):
                media = f'<img loading="lazy" src="{href}" alt="{caption}">'
            elif path.suffix.lower() in ('.webm', '.mp4'):
                media = f'<video controls preload="metadata" src="{href}"></video>'
            elif path.suffix.lower() not in ('.zip', '.trace', '.network', '.json', '.txt', '.yaml', '.yml'):
                raise ValueError('Unsupported evidence type: ' + name)
            result.append(f'<figure>{media}<figcaption><a href="{href}">{caption}</a></figcaption></figure>')
        return ''.join(result)

    sections = []
    for journey in report['journeys']:
        status = journey['status']
        if status not in ('observed', 'partial', 'blocked', 'not explored'):
            raise ValueError('Unknown journey coverage: ' + str(status))
        steps = []
        if status == 'observed' and not journey.get('steps'):
            raise ValueError('Observed journeys need action evidence')
        for step in journey.get('steps', []):
            if not step.get('action') or not step.get('observed') or not step.get('evidence'):
                raise ValueError('Each observed step needs action, result and evidence')
            steps.append(f'<li><p>{text(step["action"])}</p><p>{text(step["observed"])}</p>'
                         + evidence(step['evidence']) + '</li>')
        gaps = journey.get('gaps', '')
        if status != 'observed' and not gaps:
            raise ValueError('Incomplete journeys need an explicit gap')
        sections.append(f'<section><h2>{text(journey["name"])}</h2><p class="tag">{text(status)}</p>'
                        + '<ol>' + ''.join(steps) + '</ol><p>' + text(gaps) + '</p></section>')
    findings = []
    for finding in report.get('findings', []):
        if not finding.get('evidence'):
            raise ValueError('Findings need observation evidence')
        findings.append('<article>' + ''.join(
            f'<h3>{label}</h3><p>{text(finding[key])}</p>' for key, label in (
                ('observed', 'Observed'), ('inferred', 'Inferred'), ('recommendation', 'Recommendation')))
            + evidence(finding['evidence']) + '</article>')
    doc = '''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' data:; media-src 'self'; style-src 'unsafe-inline'">
<title>UX study</title><style>
body{font:17px/1.6 system-ui,sans-serif;background:#f4f5f7;color:#192230;margin:0}
main{max-width:1040px;margin:auto;padding:40px 24px}h1{font-size:36px;line-height:1.2}
h2{font-size:25px}h3{font-size:17px;margin-bottom:0}p{white-space:pre-wrap}
section,article{background:white;border:1px solid #dde1e7;border-radius:12px;padding:24px;margin:24px 0}
figure{margin:20px 0}img,video{width:100%;max-height:720px;object-fit:contain;background:#eef0f4;border-radius:8px}
a{color:#1747a6;overflow-wrap:anywhere}.tag{display:inline-block;background:#e8edf6;border-radius:6px;padding:3px 12px}
li{margin-bottom:16px}header p,figcaption{color:#586275}footer{margin-top:40px;font-size:14px}
</style><main><header><p>Private UX study</p>'''
    doc += '<h1>' + text(study['objective']) + '</h1><p>' + text(report['context']) + '</p></header>'
    doc += '<p>' + text(report['summary']) + '</p><section><h2>App map</h2><p>' + text(report['app_map']) + '</p></section>'
    doc += ''.join(sections) + '<h2>Findings and proposals</h2>' + ''.join(findings)
    doc += '<section><h2>Unknowns</h2><ul>' + ''.join('<li>' + text(x) + '</li>' for x in report['unknowns']) + '</ul></section>'
    doc += '<footer>Coverage is reported by the researcher. Captures do not establish customer validation or hidden backend behavior. Review private data before sharing.</footer></main></html>'
    out = folder / 'walkthrough.html'
    out.write_text(doc)
    return out


def review_server(folder, port=0):
    folder = Path(folder).resolve()

    class ReviewHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(folder), **kwargs)

        def send_head(self):
            name = unquote(urlsplit(self.path).path).lstrip('/')
            path = (folder / name).resolve()
            if not path.is_file() or not (path in (folder / 'walkthrough.html', folder / 'steps.html', folder / 'steps.md')
                                          or path.is_relative_to(folder / 'artifacts')):
                self.send_error(404)
                return None
            size = path.stat().st_size
            start, end = 0, size - 1
            requested = self.headers.get('Range')
            if requested:
                match = re.fullmatch(r'bytes=(\d*)-(\d*)', requested)
                if not match or not any(match.groups()):
                    self.send_error(416)
                    return None
                left, right = match.groups()
                if left:
                    start = int(left)
                    end = min(int(right), end) if right else end
                else:
                    start = max(0, size - int(right))
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header('Content-Range', f'bytes */{size}')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return None
            stream = path.open('rb')
            stream.seek(start)
            self.remaining = max(0, end - start + 1)
            self.send_response(206 if requested else 200)
            self.send_header('Content-Type', self.guess_type(str(path)))
            self.send_header('Content-Length', str(self.remaining))
            self.send_header('Accept-Ranges', 'bytes')
            if requested:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            self.end_headers()
            return stream

        def copyfile(self, source, output):
            while self.remaining:
                chunk = source.read(min(self.remaining, 65536))
                if not chunk:
                    break
                output.write(chunk)
                self.remaining -= len(chunk)

        def log_message(self, *args):
            pass

        def end_headers(self):
            self.send_header('Content-Security-Policy', "default-src 'none'; img-src 'self' data:; media-src 'self'; style-src 'unsafe-inline'")
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Cache-Control', 'no-store')
            super().end_headers()

    return ThreadingHTTPServer(('127.0.0.1', port), ReviewHandler)


def review_urls(folder, port):
    folder = Path(folder).resolve()
    base = f'http://127.0.0.1:{port}/'
    report = (folder / 'walkthrough.html').exists()
    trail = (folder / 'steps.html').exists() or ((folder / 'steps.json').exists() and not report)
    return [base + 'steps.html'] * trail + [base + 'walkthrough.html'] * (report or not trail)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    setup = sub.add_parser('init')
    setup.add_argument('name')
    setup.add_argument('--url', required=True)
    setup.add_argument('--objective', required=True)
    setup.add_argument('--project', default='.')
    drive = sub.add_parser('browser')
    drive.add_argument('study')
    drive.add_argument('args', nargs=argparse.REMAINDER)
    dashboard = sub.add_parser('dashboard', help='Run this study\'s interactive browser dashboard')
    dashboard.add_argument('study')
    dashboard.add_argument('--port', type=int, default=8931)
    dashboard.add_argument('--host', choices=['127.0.0.1', '0.0.0.0'], default='127.0.0.1')
    act = sub.add_parser('step', help='Perform one browser action and screenshot the result')
    act.add_argument('study')
    act.add_argument('args', nargs=argparse.REMAINDER)
    seen = sub.add_parser('note', help='Record what a step\'s screenshot shows, after looking at it')
    seen.add_argument('study')
    seen.add_argument('step', type=int)
    seen.add_argument('text')
    trail = sub.add_parser('walkthrough', help='Render the step-by-step trail once every step has a note')
    trail.add_argument('study')
    plan = sub.add_parser('charter', help='Bug bash: record one charter (one area, one posture, one sentence)')
    plan.add_argument('study')
    plan.add_argument('slug')
    plan.add_argument('goal')
    plan.add_argument('--posture', choices=POSTURES, required=True)
    said = sub.add_parser('claim', help='Bug bash: record a finding an explorer reported, before verifying it')
    said.add_argument('study')
    said.add_argument('--charter', required=True)
    said.add_argument('--kind', choices=['issue', 'warning'], default='issue')
    said.add_argument('--severity', type=int, required=True, help='1 trivial, 2 low, 3 medium, 4 high, 5 critical')
    said.add_argument('--title', required=True)
    said.add_argument('--where', required=True, help='Route or screen where it was seen')
    said.add_argument('--expected', required=True)
    said.add_argument('--actual', required=True)
    said.add_argument('--step', action='append', default=[], help='One reproduction step; repeat')
    said.add_argument('--evidence', action='append', default=[], help='Screenshot or video inside artifacts/; repeat')
    proven = sub.add_parser('confirm', help='Bug bash: confirm a finding with a repro test that fails for its reason')
    proven.add_argument('study')
    proven.add_argument('finding', type=int)
    proven.add_argument('--repro', required=True, help='The repro test file, relative to the project')
    proven.add_argument('--expect-failure', required=True,
                        help='Regular expression for the failing assertion that encodes the bug')
    proven.add_argument('--timeout', type=int, default=300)
    proven.epilog = 'Put the command that runs the repro test last, after --'
    dropped = sub.add_parser('reject', help='Bug bash: close a finding that is not a product bug')
    dropped.add_argument('study')
    dropped.add_argument('finding', type=int)
    dropped.add_argument('--bucket', choices=list(BUCKETS), required=True)
    dropped.add_argument('--reason', required=True, help='The check that settled it')
    summary = sub.add_parser('bugs', help='Bug bash: write bugs.md, confirmed bugs first')
    summary.add_argument('study')
    report = sub.add_parser('report')
    report.add_argument('study')
    serve = sub.add_parser('serve')
    serve.add_argument('study')
    serve.add_argument('--port', type=int, default=0)
    argv = sys.argv[1:]
    # `confirm` takes the repro command after `--`; split it off so its flags never reach argparse.
    run_command = []
    if argv[:1] == ['confirm'] and '--' in argv:
        argv, run_command = argv[:argv.index('--')], argv[argv.index('--') + 1:]
    args = parser.parse_args(argv)
    # New session artifacts/profile files should be private on POSIX.
    os.umask(0o077)
    try:
        if args.command == 'init':
            print(init(args.project, args.name, args.url, args.objective))
        elif args.command == 'browser':
            return browser(args.study, args.args)
        elif args.command == 'step':
            number, shot = step(args.study, args.args)
            print(f'Step {number}: look at {Path(args.study).resolve() / shot}, then `study.py note {args.study} {number} "<what it shows>"`')
        elif args.command == 'note':
            note(args.study, args.step, args.text)
        elif args.command == 'walkthrough':
            print(walkthrough(args.study))
        elif args.command == 'charter':
            charter(args.study, args.slug, args.posture, args.goal)
        elif args.command == 'claim':
            number = claim(args.study, args.charter, args.kind, args.severity, args.title, args.where,
                           args.expected, args.actual, args.step, args.evidence)
            print(f'Finding {number} is claimed, not confirmed. Triage it, then `confirm` it with a failing repro '
                  'test or `reject` it with the check that settled it')
        elif args.command == 'confirm':
            log = confirm(args.study, args.finding, args.repro, args.expect_failure, run_command, args.timeout)
            print(f'Finding {args.finding} confirmed; log {log}')
        elif args.command == 'reject':
            reject(args.study, args.finding, args.bucket, args.reason)
        elif args.command == 'bugs':
            out, unverified = bugs(args.study)
            print(out)
            if unverified:
                print(f'{unverified} finding(s) still unverified; confirm or reject each before reporting',
                      file=sys.stderr)
                return 1
        elif args.command == 'dashboard':
            if not 1 <= args.port <= 65535:
                raise ValueError('Dashboard port must be between 1 and 65535')
            print('Interactive browser control. Share only through an authenticated workspace preview.', flush=True)
            return browser(args.study, ['show', f'--port={args.port}', f'--host={args.host}'])
        elif args.command == 'serve':
            with review_server(args.study, args.port) as server:
                print('\n'.join(review_urls(args.study, server.server_port)), flush=True)
                try:
                    server.serve_forever()
                except KeyboardInterrupt:
                    pass
        else:
            print(render(args.study))
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(f'UX study: {error}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == '__main__':
    sys.exit(main())
