#!/usr/bin/env python3
"""Report a problem with jfactory itself to its maintainers, as a redacted GitHub issue.

Use it when the bundle got in the way: a script that broke (`bug`), a reference or skill that misled you (`docs`),
or a capability you needed and did not find (`feature`). Describe jfactory's behavior only, never the project's
code, content, URLs, customer data or credentials. It prints what it would send and sends nothing unless given
`--send`; sending publishes the text in a public repository.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

BUNDLE = Path(__file__).resolve().parents[1]
DEFAULT_REPOSITORY = 'https://github.com/jordymarshall/jfactory'
SECRET_NAME = re.compile(r'TOKEN|SECRET|PASSWORD|PASSWD|API_?KEY|PRIVATE|CREDENTIAL|COOKIE|SESSION|AUTH', re.I)
TOKEN_SHAPES = [
    r'\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}', r'\bgithub_pat_[A-Za-z0-9_]{20,}', r'\bsk-[A-Za-z0-9_-]{16,}',
    r'\bxox[abprs]-[A-Za-z0-9-]{10,}', r'\bAKIA[0-9A-Z]{16}\b', r'\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+',
    r'(?i)\bbearer\s+[A-Za-z0-9._~+/-]{12,}=*', r'-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----',
]
# Project names too generic to replace without mangling the text.
GENERIC = {'app', 'api', 'web', 'site', 'docs', 'test', 'tests', 'main', 'repo', 'project', 'server', 'client',
           'frontend', 'backend', 'monorepo', 'workspace'}
FIELDS = [('task', 'What I was doing'), ('expected', 'Expected'), ('actual', 'Actual'),
          ('approach', 'What I tried'), ('command', 'Command'), ('agent', 'Agent and model')]


def git(*args):
    try:
        return subprocess.run(['git', *args], capture_output=True, text=True).stdout.strip()
    except OSError:
        return ''


def installed():
    """The jfactory repository and version this bundle came from."""
    receipt = BUNDLE / '.jfactory-install.json'
    if receipt.is_file():
        data = json.loads(receipt.read_text())
        return data.get('repository') or DEFAULT_REPOSITORY, data.get('source_commit'), bool(data.get('source_dirty'))
    # Running from a jfactory checkout rather than an installed bundle.
    return DEFAULT_REPOSITORY, git('-C', str(BUNDLE), 'rev-parse', 'HEAD') or None, None


def project_names():
    """Names that identify the project this runs in, which are private to its owner."""
    names = set()
    top = git('rev-parse', '--show-toplevel')
    if top:
        names.add(Path(top).name)
    remote = git('remote', 'get-url', 'origin')
    match = re.search(r'[:/]([^/:]+)/([^/]+?)(?:\.git)?$', remote)
    if match:
        names |= {match.group(1) + '/' + match.group(2), match.group(2)}
    return {n for n in names if len(n) >= 4 and n.lower() not in GENERIC | {'jfactory'}}


def redact(text, repository, environ=None, names=()):
    environ = os.environ if environ is None else environ
    for name, value in environ.items():
        if SECRET_NAME.search(name) and len(value) >= 6:
            text = text.replace(value, f'<{name}>')
    for shape in TOKEN_SHAPES:
        text = re.sub(shape, '<token>', text)
    keep = repository.rstrip('/')
    text = re.sub(r'https?://[^\s)>\]"\']+',
                  lambda m: m.group(0) if m.group(0).startswith(keep) else '<url>', text)
    text = re.sub(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+', '<email>', text)
    text = re.sub(r'(/Users|/home)/[^/\s]+', '~', text)
    for name in sorted(names, key=len, reverse=True):
        text = re.sub(r'(?<![\w-])' + re.escape(name) + r'(?![\w-])', '<project>', text, flags=re.I)
    return text


def compose(args, repository, commit, dirty, environ=None, names=()):
    if len(args.message.split()) < 4:
        raise ValueError('Say what went wrong in one or two sentences (-m)')
    clean = lambda text: redact(text, repository, environ, names).strip()  # noqa: E731
    summary = clean(args.message)
    title = f'[feedback:{args.type}] ' + (summary if len(summary) <= 90 else summary[:87].rstrip() + '...')
    lines = [summary, '']
    for field, label in FIELDS:
        value = getattr(args, field)
        if value:
            value = clean(value)
            lines.append(f'**{label}:** ' + (f'`{value}`' if field == 'command' else value))
    version = (commit or 'unknown')[:12] + (' (modified)' if dirty else '')
    lines += ['', f'jfactory {version}, reported with `scripts/feedback.py`. Redacted automatically; the sender '
                  'reviewed it before sending.']
    return title, '\n'.join(lines) + '\n'


def slug(repository):
    match = re.search(r'github\.com[/:]([^/]+/[^/]+?)(?:\.git)?/?$', repository)
    if not match:
        raise ValueError(f'Cannot tell the GitHub repository from {repository}')
    return match.group(1)


def send(repo, title, body):
    """Comment on an open issue with the same title, or open a new one."""
    found = subprocess.run(['gh', 'issue', 'list', '--repo', repo, '--state', 'open', '--search', f'"{title}" in:title',
                            '--json', 'number,title,url'], capture_output=True, text=True, check=True)
    same = [i for i in json.loads(found.stdout or '[]') if i['title'] == title]
    if same:
        subprocess.run(['gh', 'issue', 'comment', str(same[0]['number']), '--repo', repo, '--body', body],
                       check=True, capture_output=True, text=True)
        return same[0]['url'] + ' (added to the existing report)'
    made = subprocess.run(['gh', 'issue', 'create', '--repo', repo, '--title', title, '--body', body],
                          check=True, capture_output=True, text=True)
    return made.stdout.strip()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--type', choices=['bug', 'docs', 'feature'], required=True)
    parser.add_argument('-m', '--message', required=True, help='One or two sentences: what went wrong')
    parser.add_argument('--task', help='What you were doing')
    parser.add_argument('--expected')
    parser.add_argument('--actual', help='What happened, with the error message')
    parser.add_argument('--approach', help='What you tried')
    parser.add_argument('--command', help='The jfactory command involved')
    parser.add_argument('--agent', help='Agent and model, e.g. claude/opus-5-5')
    parser.add_argument('--send', action='store_true', help='Publish it; without this, only print it')
    args = parser.parse_args(argv)
    try:
        repository, commit, dirty = installed()
        title, body = compose(args, repository, commit, dirty, names=project_names())
        if not args.send:
            print(f'Would open an issue in {slug(repository)}:\n\n# {title}\n\n{body}\nNothing was sent. Check the '
                  'text, get the owner\'s agreement, then rerun with --send.')
            return 0
        print(send(slug(repository), title, body))
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(f'Feedback error: {error}', file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        print(f'Feedback was not sent: {(error.stderr or error.stdout or "").strip()}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
