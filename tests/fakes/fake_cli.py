#!/usr/bin/env python3
"""Minimal gh and conductor fakes for coord.py tests. State lives in $FAKE_STATE."""
import json
import os
import re
import sys
import time
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
    if (db.get('strict_conductor_json') and '--json' not in args and
            args[:2] in (['session', 'status'], ['workspace', 'get'])):
        done('Status  idle\n')
    if db.get('conductor_sleep'):
        time.sleep(db['conductor_sleep'])
    if db.get('conductor_fail'):
        path.write_text(json.dumps(db))
        sys.stderr.write('conductor: service unavailable')
        sys.exit(1)
    if args[:2] == ['workspace', 'list']:
        # `listed` holds workspaces other than those this fake created; archived ones drop out of the list.
        done({'data': [w for w in db.get('listed', []) if w['id'] not in db.get('archived', [])],
              'offset': 0, 'hasMore': False})
    if args[:2] == ['project', 'list']:
        done({'data': db.get('projects', []), 'offset': 0, 'hasMore': False})
    if args[:1] == ['model']:
        done({'agents': [{'agent': 'claude', 'models': ['opus-5-5-1m', 'sonnet-5-1m'],
                          'efforts': ['low', 'medium', 'high', 'max'], 'fastModeModels': ['opus-5-5-1m']},
                         {'agent': 'codex', 'models': ['gpt-6-sol', 'gpt-6.1-sol', 'gpt-6-astra', 'gpt-6-luna', 'gpt-5.6-sol'],
                          'efforts': ['low', 'medium', 'high'], 'fastModeModels': ['gpt-6-sol', 'gpt-6.1-sol', 'gpt-6-luna']}]})
    if args[:2] == ['workspace', 'create']:
        n = len(db.setdefault('workspaces', [])) + 1
        db['workspaces'].append({'name': opt('--name'), 'branch': opt('--branch'), 'agent': opt('--agent'),
                                 'project': opt('--project-id'), 'repo_url': opt('--repo-url'),
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
    if args[:2] == ['workspace', 'archive']:
        if args[2] in db.get('archive_fail', []):
            path.write_text(json.dumps(db))
            sys.stderr.write('archive failed')
            sys.exit(1)
        db.setdefault('archived', []).append(args[2])
        if args[2] in db.get('archive_slow', []):
            # Conductor archives, but the CLI call outlives the caller's time limit (seen 2026-10-01).
            path.write_text(json.dumps(db))
            import time
            time.sleep(30)
        done()
    if args[:2] == ['section', 'list']:
        done({'data': [s for s in db.get('sections', []) if s['id'] not in db.get('deleted_sections', [])],
              'offset': 0, 'hasMore': False})
    if args[:2] == ['workspace', 'session']:
        # `workspace_sessions` lists a workspace's session ids; otherwise workspace wN has the one session sN.
        ids = db.get('workspace_sessions', {}).get(args[2])
        if ids is None:
            ids = [args[2].replace('w', 's', 1)] if args[2].startswith('w') else []
        offset = int(opt('--offset', '0'))
        # `session_replies` gives literal replies per workspace and requested offset, to simulate a broken server.
        literal = db.get('session_replies', {}).get(args[2], {}).get(str(offset))
        if literal is not None:
            done(literal)
        limit = min(int(opt('--limit', '100')), db.get('page_size', 100))  # the server may cap a page
        done({'data': [{'id': i} for i in ids[offset:offset + limit]], 'offset': offset,
              'hasMore': offset + limit < len(ids)})
    if args[:2] == ['workspace', 'get'] and db.get('conductor_sleep_get'):
        import time
        time.sleep(db['conductor_sleep_get'])
    if args[:2] == ['workspace', 'get']:
        done({'id': args[2], 'state': 'archived' if args[2] in db.get('archived', []) else 'ready'})
    if args[:2] == ['section', 'delete']:
        db.setdefault('deleted_sections', []).append(args[2])
        done({'section': {'id': args[2], 'workspaceIds': []}})
    if args[:2] == ['session', 'status']:
        if args[2] in db.get('raw_status', {}):
            done(db['raw_status'][args[2]])  # a reply exactly as given, such as '{}' or '{"status": null}'
        if db.get('sessions', {}).get(args[2]) == 'unavailable':
            path.write_text(json.dumps(db))
            sys.stderr.write('status unavailable')
            sys.exit(1)
        done({'status': db.get('sessions', {}).get(args[2], 'working')})
if tool == 'git' and args[:1] == ['show'] and args[1].endswith(':.jfactory/standards.md'):
    if 'standards' not in db:
        path.write_text(json.dumps(db))
        sys.stderr.write('fatal: path does not exist')
        sys.exit(128)
    done(db['standards'])
if tool == 'git' and args[:1] == ['show']:
    done(json.dumps(db.get('config', {'static': ['**/*.md'], 'features': {'all': {'paths': ['**']}}})))
if tool == 'git' and args[:2] == ['diff', '--name-only']:
    done('\n'.join(db.get('diff', [])))
if tool == 'gh' and db.get('gh_fail') and (args[:2] in (['pr', 'view'], ['api', 'graphql'])):
    path.write_text(json.dumps(db))
    sys.stderr.write('HTTP 502: Bad Gateway')
    sys.exit(1)
if tool == 'gh' and args[:2] == ['api', 'graphql']:
    # Mirrors GitHub: PRs it finds are answered, a missing number is null plus an error, and gh then exits 1.
    query = next(a[len('query='):] for a in args if a.startswith('query='))
    numbers = re.findall(r'p(\d+): pullRequest', query)
    found = {f'p{n}': ({'state': db['prs'][n]['state']} if 'state' in db.get('prs', {}).get(n, {}) else None)
             for n in numbers}
    path.write_text(json.dumps(db))
    reply = {'data': {'repository': found}}
    if None in found.values():
        reply['errors'] = [{'type': 'NOT_FOUND'}]
    sys.stdout.write(json.dumps(reply))
    sys.exit(1 if 'errors' in reply else 0)
if tool == 'gh' and args[:1] == ['api'] and args[1].endswith('/files'):
    number = args[1].split('/')[-2]
    done('\n'.join(db['prs'][number].get('files', ['src/x.py'])))
# pr_health.py: an Actions job, a check run's annotations, update-branch and re-runs.
if tool == 'gh' and args[:1] == ['api'] and '/actions/jobs/' in args[1]:
    done(db['jobs'][args[1].rsplit('/', 1)[1]])
if tool == 'gh' and args[:1] == ['api'] and args[1].endswith('/annotations'):
    done(db.get('annotations', {}).get(args[1].split('/')[-2], []))
if tool == 'gh' and args[:3] == ['api', '-X', 'PUT']:
    db.setdefault('updates', []).append([args[3], *[a for a in args[4:] if '=' in a]])
    done()
if tool == 'gh' and args[:2] == ['run', 'list'] and '--status' in args:
    # Workflow runs waiting for a runner, by status: {"queued_runs": {"queued": [{"databaseId", "createdAt"}]}}.
    done(db.get('queued_runs', {}).get(args[args.index('--status') + 1], []))
if tool == 'gh' and args[:2] == ['run', 'rerun']:
    db.setdefault('reruns', []).append(args[2:])
    done()
if tool == 'gh' and args[:2] == ['pr', 'list']:
    done(db.get('pr_list', []))
if tool == 'gh' and args[:1] == ['api'] and '/check-runs' in args[1]:
    done(db.get('check_runs', {'check_runs': [{'name': 'checks', 'status': 'completed', 'conclusion': 'success'}]}))
if tool == 'gh' and args[:1] == ['api'] and len(args) == 2:
    # Repository settings for setup_check.py: repos/<o>/<r>, its rules and classic protection.
    if args[1].endswith('/protection'):
        if 'protection' not in db:
            path.write_text(json.dumps(db))
            sys.stderr.write('Branch not protected (HTTP 404)')
            sys.exit(1)
        done(db['protection'])
    if '/rules/branches/' in args[1]:
        done(db.get('rules', []))
    if '/actions/variables/' in args[1]:
        name = args[1].rsplit('/', 1)[1]
        if name not in db.get('variables', {}):
            path.write_text(json.dumps(db))
            sys.stderr.write('Not Found (HTTP 404)')
            sys.exit(1)
        done({'name': name, 'value': db['variables'][name]})
    if args[1].endswith('/actions/runners'):
        done({'total_count': len(db.get('runners', [])), 'runners': db.get('runners', [])})
    if args[1].count('/') == 2:
        done(db.get('repo', {'default_branch': 'main', 'allow_auto_merge': False}))
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
        db.setdefault('labels', []).append(args[2])
        done()
    if args[:2] == ['issue', 'create']:
        n = str(len(issues) + 1)
        issues[n] = {'title': opt('--title'), 'body': Path(opt('--body-file')).read_text(), 'comments': [], 'state': 'OPEN',
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
    if args[:2] == ['issue', 'reopen']:
        issues[args[2]]['state'] = 'OPEN'
        done()
    if args[:2] == ['issue', 'list']:
        wanted = opt('--state', 'open').upper()
        done([{'number': int(k), 'title': v.get('title', 'x'), 'url': v['url'], 'state': v['state']}
              for k, v in issues.items() if wanted in ('ALL', v['state'])
              and (not opt('--label') or opt('--label') in [label['name'] for label in v.get('labels', [])])
              and (not opt('--search') or opt('--search').split('"')[1] in v.get('title', ''))][:int(opt('--limit', '30'))])
    if args[:2] == ['pr', 'view']:
        pr = db['prs'][args[2]]
        # `land_after`: GitHub merges a queued auto-merge after this many more views.
        if pr.get('autoMergeRequest') and 'land_after' in db:
            db['land_after'] -= 1
            if db['land_after'] <= 0:
                pr.update(state='MERGED', mergeCommit={'oid': 'merge5555'}, autoMergeRequest=None)
        if db.get('drop_auto_merge'):
            pr['autoMergeRequest'] = None
        # `push_head`: a writer pushes a new head after the merge is queued; auto-merge stays queued.
        if pr.get('autoMergeRequest') and db.get('push_head'):
            pr['headRefOid'] = db.pop('push_head')
        done({'baseRefName': 'main', 'comments': [], 'isCrossRepository': False, **pr})
    if args[:2] == ['pr', 'merge'] and '--disable-auto' in args:
        db['prs'][args[2]]['autoMergeRequest'] = None
        db.setdefault('disabled', []).append(args[2])
        done()
    if args[:2] == ['pr', 'merge']:
        db.setdefault('merged', []).append(args[2])
        if args[2] in db.get('prs', {}):
            db['prs'][args[2]]['autoMergeRequest'] = {'mergeMethod': 'SQUASH'}
        done()
sys.stderr.write(f'fake: unsupported {tool} {args}\n')
sys.exit(1)
