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
    for directory in (folder / 'artifacts', folder / 'artifacts' / 'steps'):
        if directory.is_symlink():
            raise ValueError('Study capture directories must not be symlinks')
    (folder / 'artifacts' / 'steps').mkdir(mode=0o700, exist_ok=True)
    shot = f'artifacts/steps/{number:03d}.png'
    started = datetime.now(timezone.utc)
    code = run(folder, list(args))
    seconds = round((datetime.now(timezone.utc) - started).total_seconds(), 2)
    captured = run(folder, ['screenshot', f'--filename={shot}'])
    ok = not captured and (folder / shot).is_file() and not (folder / shot).is_symlink()
    # Record the action either way: it happened, and the trail must not hide it.
    steps.append({'step': number, 'action': ' '.join(args), 'exit': code, 'seconds': seconds,
                  'at': started.isoformat(), 'screenshot': shot if ok else None, 'note': ''})
    write_json(log_path, steps)
    if not ok:
        raise ValueError(f'Step {number} ran, but its screenshot was not captured; the trail will not render until the '
                         'session is fixed and the journey is walked again')
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
    shots = (folder / 'artifacts' / 'steps').resolve()
    missing = []
    for s in steps:
        path = (folder / s['screenshot']).resolve() if s.get('screenshot') else None
        if not path or not path.is_relative_to(shots) or not path.is_file() or (folder / s['screenshot']).is_symlink():
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
    report = sub.add_parser('report')
    report.add_argument('study')
    serve = sub.add_parser('serve')
    serve.add_argument('study')
    serve.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
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
        elif args.command == 'dashboard':
            if not 1 <= args.port <= 65535:
                raise ValueError('Dashboard port must be between 1 and 65535')
            print('Interactive browser control. Share only through an authenticated workspace preview.', flush=True)
            return browser(args.study, ['show', f'--port={args.port}', f'--host={args.host}'])
        elif args.command == 'serve':
            with review_server(args.study, args.port) as server:
                print(f'http://127.0.0.1:{server.server_port}/walkthrough.html', flush=True)
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
