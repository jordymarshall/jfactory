#!/usr/bin/env python3
"""Capture real check commands and reject failed, stale or insufficient-scope proof."""
import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

SCOPES = {'unit', 'component', 'integration', 'application', 'provider', 'deployed', 'static', 'judgment'}
EVIDENCE = Path('.context/jfactory')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_receipt(directory, record):
    staged = directory / 'receipt.tmp'
    staged.write_text(json.dumps(record, indent=2) + '\n')
    os.replace(staged, directory / 'receipt.json')


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], stderr=subprocess.PIPE)


def root_dir():
    return Path(git(Path.cwd(), 'rev-parse', '--show-toplevel').decode().strip()).resolve()


def fingerprint(root):
    names = git(root, 'ls-files', '-z', '--cached', '--others', '--exclude-standard').split(b'\0')
    items = []
    for raw in sorted(set(names)):
        if not raw:
            continue
        name = os.fsdecode(raw)
        if Path(name).is_relative_to(EVIDENCE):
            continue
        p = root / name
        if p.is_symlink():
            value = 'link:' + os.readlink(p)
        elif p.is_file():
            value = sha(p.read_bytes()) + ':' + str(p.stat().st_mode & 0o111)
        elif p.is_dir():
            # Submodules have their own source identity; inspect recursively.
            if Path(git(p, 'rev-parse', '--show-toplevel').decode().strip()).resolve() != p.resolve():
                raise ValueError(f'Initialize the submodule before verification: {name}')
            value = 'submodule:' + fingerprint(p)
        else:
            value = 'deleted'
        items.append([name, value])
    return sha(json.dumps(items, ensure_ascii=True).encode())


def load_task(root, path):
    p = path.resolve()
    if not p.is_relative_to(root) or p.is_relative_to(root / EVIDENCE):
        raise ValueError('Acceptance file must live in the repo, outside .context/jfactory')
    task = json.loads(p.read_text())
    if not isinstance(task.get('objective'), str) or not task['objective'].strip() or not task.get('criteria'):
        raise ValueError('Task needs an objective and nonempty criteria')
    seen = set()
    for criterion in task['criteria']:
        key, scopes = criterion['id'], criterion['required_scopes']
        if not isinstance(key, str) or not key or key in seen or not criterion.get('expected'):
            raise ValueError('Criteria need unique IDs and expected behavior')
        if not isinstance(scopes, list) or not scopes or not set(scopes) <= SCOPES:
            raise ValueError('Each criterion needs valid required_scopes')
        seen.add(key)
    return task, sha(p.read_bytes()), str(p.relative_to(root))


def run(args):
    if os.name != 'posix':
        raise ValueError('Process-group capture requires POSIX; use WSL or native verification tooling')
    root = root_dir()
    task, task_hash, task_name = load_task(root, args.task)
    if args.criterion not in {c['id'] for c in task['criteria']}:
        raise ValueError('Criterion is absent from the acceptance file')
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command or args.timeout <= 0:
        raise ValueError('Provide a command and positive timeout')
    before = fingerprint(root)
    directory = root / EVIDENCE / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-' + uuid4().hex[:8])
    directory.mkdir(parents=True)
    log = directory / 'output.log'
    record = {'schema': 1, 'task': task_name, 'task_sha256': task_hash,
              'criterion': args.criterion, 'scope': args.scope, 'environment': args.environment,
              'source_before': before, 'revision': git(root, 'rev-parse', 'HEAD').decode().strip(),
              'command': command, 'cwd': str(root), 'status': 'running', 'exit_code': None,
              'started': datetime.now(timezone.utc).isoformat()}
    write_receipt(directory, record)
    process = None
    previous = {}

    def interrupted(signum, frame):
        raise InterruptedError(signum)

    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, interrupted)
        with log.open('wb') as output:
            try:
                process = subprocess.Popen(command, cwd=root, stdout=output, stderr=subprocess.STDOUT,
                                           start_new_session=True)
                record['exit_code'] = process.wait(timeout=args.timeout)
                record['status'] = 'passed' if record['exit_code'] == 0 else 'failed'
            except subprocess.TimeoutExpired:
                record.update(status='timeout', exit_code=124)
            except InterruptedError as error:
                record.update(status='interrupted', exit_code=128 + error.args[0])
            except OSError as error:
                output.write(str(error).encode())
                record.update(status='launch-failed', exit_code=127)
    finally:
        # Prevent a second cancellation from interrupting owned-process cleanup.
        for sig in previous:
            signal.signal(sig, signal.SIG_IGN)
        if process:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
        record['finished'] = datetime.now(timezone.utc).isoformat()
        record['source_after'] = fingerprint(root)
        if before != record['source_after']:
            record['status'] = 'source-changed'
        record['log_sha256'] = sha(log.read_bytes())
        write_receipt(directory, record)
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    print(json.dumps({'receipt': str(directory / 'receipt.json'), 'status': record['status']}))
    return 0 if record['status'] == 'passed' else (record['exit_code'] or 1)


def check(args):
    root = root_dir()
    task, task_hash, task_name = load_task(root, args.task)
    source = fingerprint(root)
    latest = {}
    for path in sorted((root / EVIDENCE).glob('*/receipt.json')):
        receipt = json.loads(path.read_text())
        if receipt.get('task') == task_name:
            latest[(receipt.get('criterion'), receipt.get('scope'))] = (path, receipt)
    gaps = []
    for criterion in task['criteria']:
        for scope in criterion['required_scopes']:
            key = (criterion['id'], scope)
            item = latest.get(key)
            reason = 'missing'
            if item:
                path, receipt = item
                log = path.parent / 'output.log'
                if receipt.get('task_sha256') != task_hash or receipt.get('source_before') != source or receipt.get('source_after') != source:
                    reason = 'stale'
                elif receipt.get('status') != 'passed' or receipt.get('exit_code') != 0:
                    reason = receipt.get('status', 'invalid')
                elif not log.is_file() or sha(log.read_bytes()) != receipt.get('log_sha256'):
                    reason = 'missing or changed output'
                else:
                    continue
            gaps.append({'criterion': key[0], 'scope': scope, 'reason': reason})
    print(json.dumps({'evidence_complete': not gaps, 'gaps': gaps,
                      'limits': 'Checks receipt freshness, command success and declared scopes; not test adequacy or product acceptance.'}, indent=2))
    return 1 if gaps else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='action', required=True)
    capture = commands.add_parser('run')
    capture.add_argument('--task', type=Path, required=True)
    capture.add_argument('--criterion', required=True)
    capture.add_argument('--scope', choices=sorted(SCOPES), required=True)
    capture.add_argument('--environment', required=True)
    capture.add_argument('--timeout', type=float, default=180)
    capture.add_argument('command', nargs=argparse.REMAINDER)
    verify = commands.add_parser('check')
    verify.add_argument('--task', type=Path, required=True)
    args = parser.parse_args()
    try:
        return run(args) if args.action == 'run' else check(args)
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(f'Evidence error: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
