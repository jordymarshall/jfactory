#!/usr/bin/env python3
"""Minimal gh and conductor fakes for coord.py tests. State lives in $FAKE_STATE."""
import json
import os
import sys
from pathlib import Path

path = Path(os.environ['FAKE_STATE'])
db = json.loads(path.read_text())
tool, args = sys.argv[1], sys.argv[2:]
db.setdefault('calls', []).append([tool, *args])


def opt(name, default=None):
    return args[args.index(name) + 1] if name in args else default


def done(out=''):
    path.write_text(json.dumps(db))
    sys.stdout.write(out if isinstance(out, str) else json.dumps(out))
    sys.exit(0)


if tool == 'conductor':
    if args[:1] == ['model']:
        done({'agents': [{'agent': 'claude', 'models': ['opus-5-5-1m', 'sonnet-5-1m'],
                          'efforts': ['low', 'medium', 'high', 'max'], 'fastModeModels': ['opus-5-5-1m']},
                         {'agent': 'codex', 'models': ['gpt-6-sol', 'gpt-5.6-sol'],
                          'efforts': ['low', 'medium', 'high'], 'fastModeModels': ['gpt-6-sol']}]})
    if args[:2] == ['workspace', 'create']:
        n = len(db.setdefault('workspaces', [])) + 1
        db['workspaces'].append({'name': opt('--name'), 'branch': opt('--branch'), 'agent': opt('--agent'),
                                 'model': opt('--model'), 'effort': opt('--effort'),
                                 'fast': '--fast-mode' in args, 'message': Path(opt('--message-file')).read_text()})
        # Mirrors the observed Conductor response shape.
        done({'workspaceId': f'w{n}', 'sessionId': f's{n}', 'deepLink': f'conductor://workspace?id=w{n}',
              'initialMessage': None})
    if args[:2] == ['section', 'create']:
        db['section'] = args[2]
        done({'section': {'id': 'sec1', 'name': args[2], 'workspaceIds': []}})
    if args[:2] == ['workspace', 'move']:
        db.setdefault('moves', []).append([a for a in args[2:] if a != '--section'])
        done()
    if args[:2] == ['session', 'status']:
        done({'status': db.get('sessions', {}).get(args[2], 'working')})
if tool == 'git' and args[:1] == ['show']:
    done(json.dumps(db.get('config', {'static': ['**/*.md'], 'features': {'all': {'paths': ['**']}}})))
if tool == 'git' and args[:2] == ['diff', '--name-only']:
    done('\n'.join(db.get('diff', [])))
if tool == 'gh' and args[:1] == ['api'] and args[1].endswith('/files'):
    number = args[1].split('/')[-2]
    done('\n'.join(db['prs'][number].get('files', ['src/x.py'])))
if tool == 'gh' and args[:3] == ['api', '-X', 'POST']:
    db.setdefault('statuses', []).append({a.split('=', 1)[0]: a.split('=', 1)[1] for a in args if '=' in a})
    done()
if tool == 'gh' and args[:2] == ['pr', 'comment']:
    db['prs'][args[2]].setdefault('comments', []).append(
        {'body': Path(opt('--body-file')).read_text(), 'authorAssociation': db.get('association', 'OWNER')})
    done()
if tool == 'gh':
    issues = db.setdefault('issues', {})
    if args[:2] == ['label', 'create']:
        done()
    if args[:2] == ['issue', 'create']:
        n = str(len(issues) + 1)
        issues[n] = {'body': Path(opt('--body-file')).read_text(), 'comments': [], 'state': 'OPEN',
                     'labels': [{'name': opt('--label')}], 'url': f'https://github.test/issues/{n}'}
        done(issues[n]['url'] + '\n')
    if args[:2] == ['issue', 'view']:
        done(issues[args[2]])
    if args[:2] == ['issue', 'edit']:
        issues[args[2]]['body'] = Path(opt('--body-file')).read_text()
        done()
    if args[:2] == ['issue', 'comment']:
        issue = issues[args[2]]
        issue['comments'].append({'body': Path(opt('--body-file')).read_text(),
                                  'createdAt': f"2099-01-01T00:00:{len(issue['comments']):02d}Z"})
        done()
    if args[:2] == ['issue', 'close']:
        issues[args[2]]['state'] = 'CLOSED'
        done()
    if args[:2] == ['issue', 'list']:
        done([{'number': int(k), 'title': 'x', 'url': v['url']} for k, v in issues.items() if v['state'] == 'OPEN'])
    if args[:2] == ['pr', 'view']:
        done({'baseRefName': 'main', 'comments': [], 'isCrossRepository': False, **db['prs'][args[2]]})
    if args[:2] == ['pr', 'merge']:
        db.setdefault('merged', []).append(args[2])
        done()
sys.stderr.write(f'fake: unsupported {tool} {args}\n')
sys.exit(1)
