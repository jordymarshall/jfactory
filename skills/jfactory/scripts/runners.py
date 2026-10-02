#!/usr/bin/env python3
"""Run a repository's CI on machines you own: start, list and stop single-use GitHub Actions runners in Docker.

Each job gets a fresh container that runs that one job and is then deleted, as on GitHub's hosted runners, so nothing
a job leaves behind reaches a later job. A supervisor on the host keeps `--count` idle runners ready: for each it asks
GitHub for a single-use (JIT) runner configuration, copies it into a new container and starts it. The admin token stays
on the host; containers only ever see their own single-use configuration.

The image is GitHub's runner image (Ubuntu) plus what hosted runners provide and CI steps commonly assume: gh,
python3, jq, zip, the system libraries Playwright's Chromium needs, and passwordless sudo for `apt-get`.
Workflows choose these runners through the `JFACTORY_RUNNER` repository variable (references/ci-runners.md); this
script never changes workflows or repository settings.

Minting runner configurations needs a token that can administer the repository's runners: `gh` signed in as a
repository admin, or GH_TOKEN set to a fine-grained token with "Administration: read and write" on that repository.
GitHub App tokens without that permission get HTTP 403.
"""
import argparse
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

IMAGE = 'jfactory-runner:latest'
LABEL = 'jfactory'
# The container label that marks containers this script owns, so nothing else is ever touched.
OWNER_LABEL = 'jfactory.runner'
STATE = Path(os.environ.get('JFACTORY_RUNNER_STATE') or Path.home() / '.cache' / 'jfactory-runners')
DOCKERFILE = r'''FROM ghcr.io/actions/actions-runner:latest
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git gnupg jq python3 python3-venv unzip xz-utils zip \
 && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o /usr/share/keyrings/githubcli.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list \
 && apt-get update && apt-get install -y --no-install-recommends gh \
 && rm -rf /var/lib/apt/lists/*
# Playwright's own installer adds the system libraries its browsers need, as hosted runners have them. Node is used only
# for that step and removed; workflows bring their own with actions/setup-node.
RUN arch=$(dpkg --print-architecture | sed 's/amd64/x64/') \
 && curl -fsSL "https://nodejs.org/dist/latest-v22.x/node-$(curl -fsSL https://nodejs.org/dist/latest-v22.x/SHASUMS256.txt | grep -o "v22[0-9.]*-linux-$arch.tar.xz" | head -1 | sed 's/-linux.*//')-linux-$arch.tar.xz" \
    | tar -xJ -C /opt \
 && PATH="$(echo /opt/node-v22*/bin):$PATH" npx -y playwright@latest install-deps chromium \
 && rm -rf /opt/node-v22* /root/.npm /var/lib/apt/lists/*
COPY entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh
USER runner
ENTRYPOINT ["/entrypoint.sh"]
'''
# Reads and deletes its single-use configuration, then runs exactly one job.
ENTRYPOINT = r'''#!/bin/bash
set -euo pipefail
cd /home/runner
jit=$(cat /home/runner/.jit)
rm -f /home/runner/.jit
exec ./run.sh --jitconfig "$jit"
'''


class Refused(Exception):
    pass


def run(cmd, check=True):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if check and result.returncode:
        detail = (result.stderr or result.stdout or '').strip()
        raise Refused(f'{" ".join(cmd[:3])} failed' + (f': {detail}' if detail else ''))
    return result


def need(tool):
    if not shutil.which(tool):
        raise Refused(f'`{tool}` is not installed; references/ci-runners.md lists what each machine needs')


def docker(*args, check=True):
    return run(['docker', *args], check=check)


def gh_api(*args, check=True):
    result = run(['gh', 'api', *args], check=False)
    if check and result.returncode:
        detail = (result.stderr or result.stdout).strip()
        hint = (' The signed-in token cannot administer runners: sign `gh` in as a repository admin or set GH_TOKEN to a'
                ' fine-grained token with "Administration: read and write" on this repository.') \
            if '403' in detail or 'not accessible' in detail else ''
        raise Refused(f'GitHub refused `gh api {args[-1] if args else ""}`: {detail}.{hint}')
    return result


def repo_slug(value):
    slug = value or run(['gh', 'repo', 'view', '--json', 'nameWithOwner', '-q', '.nameWithOwner']).stdout.strip()
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', slug or ''):
        raise Refused(f'Cannot tell the repository from {slug!r}; pass --repo owner/name')
    return slug


def prefix(repo, host):
    return 'jfactory-' + re.sub(r'[^a-z0-9-]+', '-', f'{repo.split("/")[1]}-{host}'.lower()).strip('-')


def files(repo):
    base = STATE / repo.replace('/', '__')
    return base.with_suffix('.pid'), base.with_suffix('.log'), base.with_suffix('.json')


def alive(pid_file):
    try:
        pid = int(pid_file.read_text())
        os.kill(pid, 0)
        # An exited process that nobody has reaped yet still answers kill 0.
        status = Path(f'/proc/{pid}/status')
        if status.exists() and '\nState:\tZ' in status.read_text():
            return None
        return pid
    except (OSError, ValueError):
        return None


def containers(repo):
    """This script's containers for the repository: {name: state}."""
    out = docker('ps', '-a', '--filter', f'label={OWNER_LABEL}={repo}', '--format', '{{.Names}}\t{{.State}}').stdout
    return dict(line.split('\t', 1) for line in out.splitlines() if '\t' in line)


def remote_runners(repo, name_prefix):
    out = gh_api(f'repos/{repo}/actions/runners', '--paginate', '-q',
                 '.runners[] | [.id, .name, .status, (.busy|tostring)] | @tsv', check=False)
    if out.returncode:
        return None
    rows = [line.split('\t') for line in out.stdout.splitlines() if line]
    return [{'id': r[0], 'name': r[1], 'status': r[2], 'busy': r[3] == 'true'} for r in rows
            if r[1].startswith(name_prefix)]


def build(pull=False):
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, 'Dockerfile').write_text(DOCKERFILE)
        Path(tmp, 'entrypoint.sh').write_text(ENTRYPOINT)
        result = subprocess.run(['docker', 'build', *(['--pull'] if pull else []), '-t', IMAGE, tmp])
        if result.returncode:
            raise Refused('docker build failed; see the output above')


def start_one(repo, config):
    """Mint a single-use runner configuration and start one fresh container with it."""
    name = f'{config["prefix"]}-{secrets.token_hex(3)}'
    labels = ['self-hosted', *config['labels']]
    minted = json.loads(gh_api('-X', 'POST', f'repos/{repo}/actions/runners/generate-jitconfig', '-f', f'name={name}',
                               '-F', 'runner_group_id=1', '-f', 'work_folder=_work',
                               *[x for label in labels for x in ('-f', f'labels[]={label}')]).stdout)
    cmd = ['create', '--rm', '--name', name, '--label', f'{OWNER_LABEL}={repo}', '--shm-size', config['shm_size']]
    if config.get('cpus'):
        cmd += ['--cpus', str(config['cpus'])]
    if config.get('memory'):
        cmd += ['--memory', config['memory']]
    try:
        docker(*cmd, IMAGE)
        # Copied in, never passed as an argument or variable, so `docker inspect` and the process list don't show it.
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, '.jit')
            path.write_text(minted['encoded_jit_config'])
            path.chmod(0o644)
            docker('cp', str(path), f'{name}:/home/runner/.jit')
        docker('start', name)
    except Refused:
        # A half-made runner would count as ready and stay registered on GitHub; remove both.
        docker('rm', '-f', name, check=False)
        runner_id = (minted.get('runner') or {}).get('id')
        if runner_id:
            gh_api('-X', 'DELETE', f'repos/{repo}/actions/runners/{runner_id}', check=False)
        raise
    return name


def reconcile(repo, config, log=print):
    """Keep `count` runners waiting for a job; each runner's container deletes itself after its one job."""
    running = [n for n, state in containers(repo).items() if state in ('running', 'created')]
    started = []
    for _ in range(config['count'] - len(running)):
        started.append(start_one(repo, config))
    if started:
        log(f'{time.strftime("%H:%M:%S")} started {", ".join(started)}')
    return started


def cmd_serve(args):
    need('docker')
    need('gh')
    repo = repo_slug(args.repo)
    pid_file, _, config_file = files(repo)
    config = json.loads(config_file.read_text())
    if not args.once:
        pid_file.write_text(str(os.getpid()))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    delay = 5
    while True:
        try:
            reconcile(repo, config, log=lambda m: print(m, flush=True))
            delay = 5
        except Refused as exc:
            # Keep serving: GitHub or Docker may recover, and a stopped supervisor would silently stall CI.
            print(f'{time.strftime("%H:%M:%S")} {exc}', flush=True)
            delay = min(delay * 2, 300)
        if args.once:
            break
        time.sleep(delay)
    return 0


def cmd_up(args):
    need('docker')
    need('gh')
    repo = repo_slug(args.repo)
    if args.count < 1:
        raise Refused('--count must be at least 1')
    STATE.mkdir(parents=True, exist_ok=True)
    pid_file, log_file, config_file = files(repo)
    labels = list(dict.fromkeys([LABEL, *[x.strip() for x in args.labels.split(',') if x.strip()]]))
    config = {'count': args.count, 'labels': labels, 'prefix': prefix(repo, args.host or os.uname().nodename.split('.')[0]),
              'cpus': args.cpus, 'memory': args.memory, 'shm_size': args.shm_size}
    if args.build or docker('image', 'inspect', IMAGE, check=False).returncode:
        build(args.pull)
    # Prove the token works before leaving a supervisor running in the background.
    gh_api(f'repos/{repo}/actions/runners', '-q', '.total_count')
    config_file.write_text(json.dumps(config))
    pid = alive(pid_file)
    if pid:
        print(f'Supervisor already running (pid {pid}); it picks up the new settings on its next start.')
        os.kill(pid, signal.SIGTERM)
        time.sleep(1)
    with open(log_file, 'a') as log:
        proc = subprocess.Popen([sys.executable, os.path.abspath(__file__), 'serve', '--repo', repo],
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    pid_file.write_text(str(proc.pid))
    print(f'Supervisor {proc.pid} keeps {args.count} single-use runner(s) ready for {repo} with labels '
          f'self-hosted,{",".join(labels)}; log: {log_file}')
    print(f'Route workflows here with the repository variable JFACTORY_RUNNER={json.dumps(["self-hosted", LABEL])}.')
    return 0


def cmd_down(args):
    need('docker')
    repo = repo_slug(args.repo)
    pid_file, _, config_file = files(repo)
    pid = alive(pid_file)
    if pid:
        os.kill(pid, signal.SIGTERM)
    pid_file.unlink(missing_ok=True)
    name_prefix = json.loads(config_file.read_text())['prefix'] if config_file.exists() else 'jfactory-'
    deadline = time.monotonic() + args.wait * 60
    while True:
        remote = remote_runners(repo, name_prefix)
        busy = {r['name'] for r in remote or [] if r['busy']}
        if not busy or args.force or time.monotonic() > deadline:
            break
        print(f'Waiting for {len(busy)} running job(s) to finish: {", ".join(sorted(busy))}', flush=True)
        time.sleep(15)
    removed, failed = 0, []
    for name in containers(repo):
        if name in busy and not args.force:
            failed.append(f'{name} (still running a job; rerun with --force to stop it)')
            continue
        docker('rm', '-f', name, check=False)
        removed += 1
    for runner in remote_runners(repo, name_prefix) or []:
        if runner['busy'] and not args.force:
            continue
        if gh_api('-X', 'DELETE', f'repos/{repo}/actions/runners/{runner["id"]}', check=False).returncode:
            failed.append(f'{runner["name"]} (GitHub refused removal; remove it in Settings > Actions > Runners)')
    print(f'Supervisor stopped; removed {removed} container(s) for {repo}.')
    for item in failed:
        print(f'Check: {item}', file=sys.stderr)
    return 1 if failed else 0


def cmd_status(args):
    need('docker')
    repo = repo_slug(args.repo)
    pid_file, log_file, config_file = files(repo)
    pid = alive(pid_file)
    config = json.loads(config_file.read_text()) if config_file.exists() else {}
    print(f'Supervisor: {"running, pid " + str(pid) if pid else "not running"}'
          + (f'; keeps {config["count"]} ready; log {log_file}' if config else ''))
    remote = {r['name']: r for r in remote_runners(repo, config.get('prefix', 'jfactory-')) or []}
    for name, state in sorted(containers(repo).items()):
        r = remote.get(name)
        print(f'{name}\tcontainer {state}\t' + (f'GitHub {r["status"]}{" busy" if r["busy"] else " idle"}'
                                                  if r else 'GitHub not yet listed'))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = p.add_subparsers(dest='command', required=True)
    up = sub.add_parser('up', help='Build the image if needed and start the supervisor that keeps runners ready')
    up.add_argument('--repo', help='owner/name; defaults to the current checkout')
    up.add_argument('--count', type=int, default=max(1, (os.cpu_count() or 2) // 2),
                    help='Runners kept ready for jobs at once on this machine (default: half the CPUs)')
    up.add_argument('--labels', default='', help='Extra comma-separated labels after self-hosted and jfactory')
    up.add_argument('--host', help='Machine name used in runner names (default: hostname)')
    up.add_argument('--cpus', type=float, help='CPU limit per runner')
    up.add_argument('--memory', help='Memory limit per runner, for example 6g; needs Docker with the cgroup memory controller')
    up.add_argument('--shm-size', default='2g', help='Shared memory per runner; browsers need more than the default')
    up.add_argument('--build', action='store_true', help='Rebuild the image even when it exists')
    up.add_argument('--pull', action='store_true', help='Pull the newest base image when building')
    serve = sub.add_parser('serve', help='The supervisor loop that `up` starts in the background')
    serve.add_argument('--repo')
    serve.add_argument('--once', action='store_true', help='Reconcile once and exit')
    down = sub.add_parser('down', help="Stop the supervisor and remove this machine's runners for the repository")
    down.add_argument('--repo')
    down.add_argument('--wait', type=float, default=30, help='Minutes to wait for running jobs before giving up')
    down.add_argument('--force', action='store_true', help='Stop runners even in the middle of a job')
    status = sub.add_parser('status', help="Show the supervisor, this machine's runners and their GitHub state")
    status.add_argument('--repo')
    args = p.parse_args(argv)
    try:
        return {'up': cmd_up, 'serve': cmd_serve, 'down': cmd_down, 'status': cmd_status}[args.command](args)
    except Refused as exc:
        print(f'Refused: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
