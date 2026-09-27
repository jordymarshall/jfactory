#!/usr/bin/env python3
"""Private UX study folders, named Playwright CLI sessions and local walkthroughs."""
import argparse
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
    env = os.environ.copy()
    env.pop('PLAYWRIGHT_CLI_SESSION', None)
    return subprocess.run(command, cwd=folder, env=env).returncode


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
            if not path.is_file() or not (path == folder / 'walkthrough.html' or path.is_relative_to(folder / 'artifacts')):
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
    return 0


if __name__ == '__main__':
    sys.exit(main())
