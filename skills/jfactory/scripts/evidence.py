#!/usr/bin/env python3
"""Capture real check commands and reject failed, stale or insufficient-scope proof."""
import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_plan  # noqa: E402

SCOPES = {'unit', 'component', 'integration', 'application', 'provider', 'deployed', 'static', 'judgment'}
EVIDENCE = Path('.context/jfactory')


# Failures that happen before a test can assert anything: a missing module, a syntax error, a runner that could not
# collect the test. A run that shows one proves nothing about the bug, whatever else its output contains.
SETUP_FAILURES = re.compile(r'ModuleNotFoundError|ImportError: |SyntaxError: |IndentationError: |Cannot find module|'
                            r'ERR_MODULE_NOT_FOUND|error TS\d{4}|COLLECTION_ERROR|errors? during collection|'
                            r'collected 0 items|No tests? found|command not found', re.I)


def failure_gap(output, pattern, sources=()):
    """Why a failing run's output does not show the expected assertion failure, or None when it does.

    Lines that echo the test's own source are ignored: tracebacks and code frames print the failing line, so a test
    that never reached its assertion could otherwise match the assertion's own message."""
    setup = SETUP_FAILURES.search(output)
    if setup:
        return f'it failed before asserting anything ({setup.group(0).strip()})'
    echoed = {line.strip() for text in sources for line in text.splitlines() if len(line.strip()) >= 8}
    observed = '\n'.join(line for line in output.splitlines() if not any(e in line for e in echoed))
    if not pattern.search(observed):
        return f'its output does not match {pattern.pattern!r} outside lines that echo the test source'
    return None


def source_texts(paths):
    """Text of the kept test files, for `failure_gap` to recognise echoed source."""
    texts = []
    for path in paths:
        for item in ([path] if path.is_file() else sorted(path.rglob('*'))):
            if item.is_file() and not item.is_symlink() and item.stat().st_size <= 1_000_000:
                texts.append(item.read_bytes().decode(errors='replace'))
    return texts


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
        if 'judgment' in scopes and not str(criterion.get('rubric') or '').strip():
            raise ValueError(f'Criterion {key} needs a judgment rubric agreed before building')
        if not isinstance(criterion.get('regression', False), bool):
            raise ValueError(f'Criterion {key}: "regression" must be true or false')
        seen.add(key)
    return task, sha(p.read_bytes()), str(p.relative_to(root))


def criterion_arg(task, key, scope):
    if key not in {c['id'] for c in task['criteria']}:
        raise ValueError('Criterion is absent from the acceptance file')
    if scope == 'judgment':
        raise ValueError('A command cannot prove a judgment; record the independent score with `judge`')


def command_arg(args):
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command or args.timeout <= 0:
        raise ValueError('Provide a command and positive timeout')
    return command


def new_directory(root):
    directory = root / EVIDENCE / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-' + uuid4().hex[:8])
    directory.mkdir(parents=True)
    return directory


def execute(command, cwd, log, timeout):
    """Run a command in its own process group, log its output and return (status, exit code). Owned processes
    are killed afterwards, even on interruption."""
    process = None
    previous = {}

    def interrupted(signum, frame):
        raise InterruptedError(signum)

    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            previous[sig] = signal.signal(sig, interrupted)
        with log.open('wb') as output:
            try:
                process = subprocess.Popen(command, cwd=cwd, stdout=output, stderr=subprocess.STDOUT,
                                           start_new_session=True)
                code = process.wait(timeout=timeout)
                result = ('passed' if code == 0 else 'failed', code)
            except subprocess.TimeoutExpired:
                result = ('timeout', 124)
            except InterruptedError as error:
                result = ('interrupted', 128 + error.args[0])
            except OSError as error:
                output.write(str(error).encode())
                result = ('launch-failed', 127)
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
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return result


def run(args):
    if os.name != 'posix':
        raise ValueError('Process-group capture requires POSIX; use WSL or native verification tooling')
    root = root_dir()
    task, task_hash, task_name = load_task(root, args.task)
    criterion_arg(task, args.criterion, args.scope)
    command = command_arg(args)
    before = fingerprint(root)
    directory = new_directory(root)
    log = directory / 'output.log'
    record = {'schema': 1, 'task': task_name, 'task_sha256': task_hash,
              'criterion': args.criterion, 'scope': args.scope, 'environment': args.environment,
              'source_before': before, 'revision': git(root, 'rev-parse', 'HEAD').decode().strip(),
              'command': command, 'cwd': str(root), 'status': 'running', 'exit_code': None,
              'started': datetime.now(timezone.utc).isoformat()}
    write_receipt(directory, record)
    try:
        record['status'], record['exit_code'] = execute(command, root, log, args.timeout)
    finally:
        record['finished'] = datetime.now(timezone.utc).isoformat()
        record['source_after'] = fingerprint(root)
        if before != record['source_after']:
            record['status'] = 'source-changed'
        record['log_sha256'] = sha(log.read_bytes())
        write_receipt(directory, record)
    print(json.dumps({'receipt': str(directory / 'receipt.json'), 'status': record['status']}))
    return 0 if record['status'] == 'passed' else (record['exit_code'] or 1)


def inside(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root) or path == root or not path.exists():
        raise ValueError(f'{name} must be an existing path inside the repository')
    return path


def contrast(args):
    """Prove a fix: the same check fails on the base revision, for the reported reason, and passes on this tree.

    The base runs in a temporary worktree. `--keep` copies the regression test (and anything else the check
    needs from this tree) over the base's files, so the new test runs against the old code; `--link` points at
    ignored dependency folders such as node_modules instead of installing them twice."""
    if os.name != 'posix':
        raise ValueError('Process-group capture requires POSIX; use WSL or native verification tooling')
    root = root_dir()
    task, task_hash, task_name = load_task(root, args.task)
    criterion_arg(task, args.criterion, args.scope)
    command = command_arg(args)
    try:
        expected = re.compile(args.expect_failure)
    except re.error as error:
        raise ValueError(f'--expect-failure is not a valid regular expression: {error}')
    keep = [inside(root, name) for name in args.keep]
    link = [inside(root, name) for name in args.link]
    base = git(root, 'rev-parse', '--verify', args.base + '^{commit}').decode().strip()
    before = fingerprint(root)
    directory = new_directory(root)
    base_log, log = directory / 'base.log', directory / 'output.log'
    record = {'schema': 1, 'kind': 'contrast', 'task': task_name, 'task_sha256': task_hash,
              'criterion': args.criterion, 'scope': args.scope, 'environment': args.environment,
              'source_before': before, 'revision': git(root, 'rev-parse', 'HEAD').decode().strip(),
              'base': args.base, 'base_revision': base, 'expect_failure': args.expect_failure,
              'kept': [str(p.relative_to(root)) for p in keep], 'command': command, 'cwd': str(root),
              'status': 'running', 'exit_code': None, 'started': datetime.now(timezone.utc).isoformat()}
    write_receipt(directory, record)
    worktree = Path(tempfile.mkdtemp(prefix='jfactory-contrast-')) / 'base'
    try:
        git(root, 'worktree', 'add', '--detach', '--quiet', str(worktree), base)
        try:
            for path in keep:
                target = worktree / path.relative_to(root)
                if target.is_dir() and not target.is_symlink():
                    shutil.rmtree(target)
                elif target.exists() or target.is_symlink():
                    target.unlink()
                target.parent.mkdir(parents=True, exist_ok=True)
                (shutil.copytree if path.is_dir() else shutil.copy2)(path, target)
            for path in link:
                target = worktree / path.relative_to(root)
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.symlink_to(path)
            record['base_status'], record['base_exit_code'] = execute(command, worktree, base_log, args.timeout)
        finally:
            subprocess.run(['git', '-C', str(root), 'worktree', 'remove', '--force', str(worktree)],
                           capture_output=True)
            shutil.rmtree(worktree.parent, ignore_errors=True)
        gap = failure_gap(base_log.read_bytes().decode(errors='replace'), expected, source_texts(keep))
        record['base_matched'] = gap is None
        if gap:
            record['base_reason'] = gap
        head_status, record['exit_code'] = execute(command, root, log, args.timeout)
        if record['base_status'] != 'failed':
            # A pass means the bug did not reproduce; a timeout or launch error proves nothing about it.
            record['status'] = 'base-passed' if record['base_status'] == 'passed' else 'base-' + record['base_status']
        elif not record['base_matched']:
            record['status'] = 'base-failed-differently'
        else:
            record['status'] = head_status
    finally:
        record['finished'] = datetime.now(timezone.utc).isoformat()
        record['source_after'] = fingerprint(root)
        if before != record['source_after']:
            record['status'] = 'source-changed'
        for name, path in (('base_log_sha256', base_log), ('log_sha256', log)):
            if path.is_file():
                record[name] = sha(path.read_bytes())
        if record['status'] == 'running':
            record['status'] = 'error'
        write_receipt(directory, record)
    print(json.dumps({'receipt': str(directory / 'receipt.json'), 'status': record['status'],
                      'base': record.get('base_status'), 'base_matched': record.get('base_matched'),
                      **({'base_reason': record['base_reason']} if record.get('base_reason') else {})}))
    return 0 if record['status'] == 'passed' else 1


def judge(args):
    """Record an independent reviewer's rubric score for a judgment criterion."""
    root = root_dir()
    task, task_hash, task_name = load_task(root, args.task)
    criterion = next((c for c in task['criteria'] if c['id'] == args.criterion), None)
    if not criterion or 'judgment' not in criterion['required_scopes']:
        raise ValueError('Criterion is absent or does not require judgment')
    refusal = verify_plan.same_family_refusal(args.judge, args.implementer, False)
    if refusal:
        raise ValueError(f'The judge must be independent: {refusal}')
    inspected = []
    for item in args.inspected:
        if re.match(r'^https?://', item):
            inspected.append({'url': item})
            continue
        path = (root / item).resolve()
        if not path.is_file() or not path.is_relative_to(root):
            raise ValueError(f'Inspected artifact {item} is not a file in the repository or an http(s) link')
        inspected.append({'path': item, 'sha256': sha(path.read_bytes())})
    source = fingerprint(root)
    directory = new_directory(root)
    log = directory / 'output.log'
    log.write_text(f'Rubric: {criterion["rubric"]}\nScores: {args.scores}\nResult: {args.result}\n')
    passed = args.result == 'pass'
    record = {'schema': 1, 'kind': 'judgment', 'task': task_name, 'task_sha256': task_hash,
              'criterion': args.criterion, 'scope': 'judgment', 'judge': args.judge,
              'implementer': args.implementer, 'inspected': inspected, 'scores': args.scores,
              'source_before': source, 'source_after': source,
              'revision': git(root, 'rev-parse', 'HEAD').decode().strip(),
              'status': 'passed' if passed else 'failed', 'exit_code': 0 if passed else 1,
              'log_sha256': sha(log.read_bytes()), 'finished': datetime.now(timezone.utc).isoformat()}
    write_receipt(directory, record)
    print(json.dumps({'receipt': str(directory / 'receipt.json'), 'status': record['status']}))
    return 0 if passed else 1


def receipt_gap(path, receipt, task_hash, source, scope):
    """Why a receipt does not prove its criterion now, or None when it does."""
    log = path.parent / 'output.log'
    if receipt.get('task_sha256') != task_hash or receipt.get('source_before') != source or receipt.get('source_after') != source:
        return 'stale'
    if scope == 'judgment' and receipt.get('kind') != 'judgment':
        return 'not an independent judgment'
    if receipt.get('status') != 'passed' or receipt.get('exit_code') != 0:
        return receipt.get('status', 'invalid')
    if not log.is_file() or sha(log.read_bytes()) != receipt.get('log_sha256'):
        return 'missing or changed output'
    if receipt.get('kind') == 'contrast':
        base_log = path.parent / 'base.log'
        if not base_log.is_file() or sha(base_log.read_bytes()) != receipt.get('base_log_sha256'):
            return 'missing or changed base output'
    return None


def check(args):
    root = root_dir()
    task, task_hash, task_name = load_task(root, args.task)
    source = fingerprint(root)
    latest, contrasts = {}, {}
    for path in sorted((root / EVIDENCE).glob('*/receipt.json')):
        receipt = json.loads(path.read_text())
        if receipt.get('task') == task_name:
            latest[(receipt.get('criterion'), receipt.get('scope'))] = (path, receipt)
            if receipt.get('kind') == 'contrast':
                contrasts[receipt.get('criterion')] = (path, receipt)
    gaps = []
    for criterion in task['criteria']:
        for scope in criterion['required_scopes']:
            item = latest.get((criterion['id'], scope))
            reason = receipt_gap(*item, task_hash, source, scope) if item else 'missing'
            if reason:
                gaps.append({'criterion': criterion['id'], 'scope': scope, 'reason': reason})
        if criterion.get('regression'):
            # A fix is proven only by the same check failing before it and passing after it.
            item = contrasts.get(criterion['id'])
            reason = receipt_gap(*item, task_hash, source, item[1].get('scope')) if item else 'missing'
            if reason:
                gaps.append({'criterion': criterion['id'], 'scope': 'contrast', 'reason': reason})
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
    before = commands.add_parser('contrast', help='Prove a fix: the check fails on the base for the reported '
                                 'reason and passes on this tree')
    before.add_argument('--task', type=Path, required=True)
    before.add_argument('--criterion', required=True)
    before.add_argument('--scope', choices=sorted(SCOPES), required=True)
    before.add_argument('--environment', required=True)
    before.add_argument('--base', required=True, help='Revision without the fix, e.g. origin/main')
    before.add_argument('--expect-failure', required=True,
                        help='Regular expression the base output must match: the assertion that encodes the bug, '
                             'so a base that fails for another reason (a missing import, a crash) proves nothing')
    before.add_argument('--keep', action='append', default=[],
                        help='Path copied from this tree into the base before running, such as the new regression '
                             'test; repeat')
    before.add_argument('--link', action='append', default=[],
                        help='Ignored dependency folder linked into the base, such as node_modules; repeat')
    before.add_argument('--timeout', type=float, default=180)
    before.add_argument('command', nargs=argparse.REMAINDER)
    score = commands.add_parser('judge', help='Record an independent rubric score for a judgment criterion')
    score.add_argument('--task', type=Path, required=True)
    score.add_argument('--criterion', required=True)
    score.add_argument('--judge', required=True, help='agent/model of the independent reviewer')
    score.add_argument('--implementer', required=True, help='agent/model that built the change')
    score.add_argument('--result', choices=['pass', 'fail'], required=True)
    score.add_argument('--scores', required=True, help='Score per rubric point, e.g. "1 yes; 2 yes; 3 no"')
    score.add_argument('--inspected', action='append', required=True,
                       help='Artifact the judge inspected: a repository file or an http(s) link; repeat')
    verify = commands.add_parser('check')
    verify.add_argument('--task', type=Path, required=True)
    args = parser.parse_args()
    try:
        return {'run': run, 'contrast': contrast, 'judge': judge, 'check': check}[args.action](args)
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(f'Evidence error: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
