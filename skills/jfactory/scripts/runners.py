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
# Separate pools on one machine, such as `deploy`: own runner label, settings and containers.
POOL_LABEL = 'jfactory.pool'
STATE = Path(os.environ.get('JFACTORY_RUNNER_STATE') or Path.home() / '.cache' / 'jfactory-runners')
# The Playwright release whose system-library list the image installs; bump it with the projects' Playwright.
PLAYWRIGHT_DEPS = '1.61.1'
DOCKERFILE = r'''FROM ghcr.io/actions/actions-runner:latest
ARG PLAYWRIGHT_DEPS
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
 && PATH="$(echo /opt/node-v22*/bin):$PATH" npx -y playwright@${PLAYWRIGHT_DEPS} install-deps chromium \
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


# Folders inside the shared cache, and the variables that point each tool at its folder.
CACHE_ENV = {'RUNNER_TOOL_CACHE': '/cache/toolcache', 'npm_config_cache': '/cache/npm',
             'PLAYWRIGHT_BROWSERS_PATH': '/cache/ms-playwright', 'JFACTORY_RUNNER_CACHE': '/cache'}
CACHE_DIRS = ('toolcache', 'npm', 'ms-playwright')


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


def prefix(repo, host, pool=''):
    return 'jfactory-' + re.sub(r'[^a-z0-9-]+', '-', f'{pool + "-" if pool else ""}{repo.split("/")[1]}-{host}'.lower()).strip('-')


def check_pool(pool):
    if pool and not re.fullmatch(r'[a-z][a-z0-9]{0,19}', pool):
        raise Refused(f'--pool must be lowercase letters and digits, starting with a letter; got {pool!r}')
    return pool or ''


def files(repo, pool=''):
    base = STATE / (repo.replace('/', '__') + (f'--{pool}' if pool else ''))
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


def containers(repo, pool=''):
    """This script's containers for the repository and pool: {name: state}."""
    out = docker('ps', '-a', '--filter', f'label={OWNER_LABEL}={repo}', '--format',
                 '{{.Names}}\t{{.State}}\t{{.Label "%s"}}' % POOL_LABEL).stdout
    rows = [(line.split('\t') + ['', ''])[:3] for line in out.splitlines() if '\t' in line]
    return {name: state for name, state, owner in rows if owner == pool}


def remote_runners(repo, name_prefix):
    out = gh_api(f'repos/{repo}/actions/runners', '--paginate', '-q',
                 '.runners[] | [.id, .name, .status, (.busy|tostring)] | @tsv', check=False)
    if out.returncode:
        return None
    rows = [line.split('\t') for line in out.stdout.splitlines() if line]
    return [{'id': r[0], 'name': r[1], 'status': r[2], 'busy': r[3] == 'true'} for r in rows
            if r[1].startswith(name_prefix + '-')]


def build(pull=False):
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, 'Dockerfile').write_text(DOCKERFILE)
        Path(tmp, 'entrypoint.sh').write_text(ENTRYPOINT)
        result = subprocess.run(['docker', 'build', *(['--pull'] if pull else []), '--build-arg',
                                 f'PLAYWRIGHT_DEPS={PLAYWRIGHT_DEPS}', '-t', IMAGE, tmp])
        if result.returncode:
            raise Refused('docker build failed; see the output above')


def cpu_list(cpu_range=None):
    """The CPUs a pool may use: all of them, or a range such as "0-5" that keeps other work (a UX loop, a deploy
    pool) on the rest of the machine."""
    if not cpu_range:
        return list(range(os.cpu_count() or 1))
    cpus = []
    for part in str(cpu_range).split(','):
        first, _, last = part.strip().partition('-')
        cpus += list(range(int(first), int(last or first) + 1))
    return cpus


def cpu_slice(slot, count, cpu_range=None):
    """The CPUs runner `slot` of `count` may use. Tools size their workers by the CPUs they can see (Vitest and Jest
    start one worker per CPU), so an unpinned container on a big machine starts many workers per job and the machine
    runs out of memory; a slice makes each job behave as on a hosted runner with the same CPUs."""
    cpus = cpu_list(cpu_range)
    size = max(1, len(cpus) // count)
    first = (slot * size) % len(cpus)
    return ','.join(str(c) for c in cpus[first:first + size])


def free_slot(repo, count, pool=''):
    """The slot for a new runner: a free one, else the least-used one. Only running or created containers hold a
    slot. A finished container that Docker is still removing once made every slot look taken, and the old fallback
    to slot 0 then put two jobs on the same CPUs while others sat idle."""
    out = docker('ps', '-a', '--filter', f'label={OWNER_LABEL}={repo}', '--format',
                 '{{.Label "jfactory.slot"}}\t{{.Label "%s"}}\t{{.State}}' % POOL_LABEL).stdout
    rows = [(line.split('\t') + ['', ''])[:3] for line in out.splitlines() if line.strip()]
    used = [int(slot) for slot, owner, state in rows
            if slot.isdigit() and owner == pool and state in ('running', 'created')]
    return min(range(count), key=lambda n: (used.count(n), n))


def prepare_cache(cache_dir):
    """Create the shared cache folders, owned by the image's `runner` user, unless they already exist. Docker would
    create a missing mount folder as root, which jobs can't write to; a container running as root inside the image
    sets the owner, so the supervisor needs no root on the host."""
    root = Path(cache_dir)
    if root.is_dir() and all((root / d).is_dir() for d in CACHE_DIRS):
        return
    script = f'mkdir -p {" ".join("/cache/" + d for d in CACHE_DIRS)} && chown runner:runner /cache ' + \
        ' '.join('/cache/' + d for d in CACHE_DIRS)
    docker('run', '--rm', '--user', 'root', '--entrypoint', 'sh', '-v', f'{root}:/cache', IMAGE, '-c', script)


def start_one(repo, config):
    """Mint a single-use runner configuration and start one fresh container with it."""
    if config.get('cache_dir'):
        prepare_cache(config['cache_dir'])  # before minting, so a failure leaves no registration behind
    name = f'{config["prefix"]}-{secrets.token_hex(3)}'
    labels = ['self-hosted', *config['labels']]
    minted = json.loads(gh_api('-X', 'POST', f'repos/{repo}/actions/runners/generate-jitconfig', '-f', f'name={name}',
                               '-F', 'runner_group_id=1', '-f', 'work_folder=_work',
                               *[x for label in labels for x in ('-f', f'labels[]={label}')]).stdout)
    pool = config.get('pool', '')
    slot = free_slot(repo, config['count'], pool)
    cmd = ['create', '--rm', '--name', name, '--label', f'{OWNER_LABEL}={repo}', '--label', f'jfactory.slot={slot}',
           '--shm-size', config['shm_size']]
    if pool:
        cmd += ['--label', f'{POOL_LABEL}={pool}']
    if config.get('pin_cpus', True):
        cmd += ['--cpuset-cpus', cpu_slice(slot, config['count'], config.get('cpu_range'))]
    if config.get('cpus'):
        cmd += ['--cpus', str(config['cpus'])]
    if config.get('memory'):
        cmd += ['--memory', config['memory']]
    if config.get('cache_dir'):
        # Shared between jobs on this machine: downloads only (Node, npm packages, browsers, build caches). Each job's
        # workspace is still the fresh container's own, so no job sees another's checkout or files.
        cmd += ['-v', f'{config["cache_dir"]}:/cache']
        for key, value in CACHE_ENV.items():
            cmd += ['-e', f'{key}={value}']
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
    running = [n for n, state in containers(repo, config.get('pool', '')).items() if state in ('running', 'created')]
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
    pool = check_pool(args.pool)
    pid_file, _, config_file = files(repo, pool)
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
    pool = check_pool(args.pool)
    if pool and args.cache_dir and not args.pr_jobs:
        raise Refused('A pool keeps no shared cache folder: its jobs (deploys, releases) must not run tools other jobs '
                      'could have written. Drop --cache-dir for --pool, or add --pr-jobs for a pool that only runs '
                      'pull-request jobs, like the main pool.')
    if pool == 'deploy' and args.pr_jobs:
        raise Refused('The deploy pool holds production secrets; it never runs pull-request jobs.')
    STATE.mkdir(parents=True, exist_ok=True)
    pid_file, log_file, config_file = files(repo, pool)
    # A pool's runners carry only their own label, so jobs asking for `jfactory` never land on them.
    own = f'{LABEL}-{pool}' if pool else LABEL
    labels = list(dict.fromkeys([own, *[x.strip() for x in args.labels.split(',') if x.strip()]]))
    config = {'count': args.count, 'labels': labels, 'pool': pool,
              'prefix': prefix(repo, args.host or os.uname().nodename.split('.')[0], pool),
              'cpus': args.cpus, 'cpu_range': args.cpu_range, 'memory': args.memory, 'shm_size': args.shm_size,
              'cache_dir': os.path.abspath(args.cache_dir) if args.cache_dir else None}
    if args.no_pin:
        # Small jobs (planning, gates, polling a deploy) share every CPU under a --cpus limit instead of a slice.
        config['pin_cpus'] = False
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
        proc = subprocess.Popen([sys.executable, os.path.abspath(__file__), 'serve', '--repo', repo,
                                 *(['--pool', pool] if pool else [])],
                                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    pid_file.write_text(str(proc.pid))
    print(f'Supervisor {proc.pid} keeps {args.count} single-use runner(s) ready for {repo} with labels '
          f'self-hosted,{",".join(labels)}; log: {log_file}')
    variable = {'deploy': 'JFACTORY_DEPLOY_RUNNER', 'light': 'JFACTORY_LIGHT_RUNNER'}.get(pool, 'JFACTORY_RUNNER')
    print(f'Route workflows here with the repository variable {variable}={json.dumps(["self-hosted", own])}.')
    return 0


def cmd_down(args):
    need('docker')
    repo = repo_slug(args.repo)
    pool = check_pool(args.pool)
    pid_file, _, config_file = files(repo, pool)
    pid = alive(pid_file)
    if pid:
        os.kill(pid, signal.SIGTERM)
    pid_file.unlink(missing_ok=True)
    name_prefix = json.loads(config_file.read_text())['prefix'] if config_file.exists() else 'jfactory-'
    deadline = time.monotonic() + args.wait * 60
    while True:
        remote = remote_runners(repo, name_prefix)
        if remote is None and not args.force:
            # Without GitHub's list we can't tell which runners are mid-job; stopping them all could kill a job.
            raise Refused('GitHub did not list the runners, so running jobs are unknown; rerun when GitHub answers, '
                          'or pass --force to stop them anyway')
        busy = {r['name'] for r in remote or [] if r['busy']}
        if not busy or args.force or time.monotonic() > deadline:
            break
        print(f'Waiting for {len(busy)} running job(s) to finish: {", ".join(sorted(busy))}', flush=True)
        time.sleep(15)
    removed, failed = 0, []
    for name in containers(repo, pool):
        if name in busy and not args.force:
            failed.append(f'{name} (still running a job; rerun with --force to stop it)')
            continue
        docker('rm', '-f', name, check=False)
        removed += 1
    leftover = remote_runners(repo, name_prefix)
    if leftover is None:
        failed.append('GitHub did not list the runners, so their registrations may remain; check Settings > Actions > '
                      'Runners (single-use runners drop off once offline)')
    for runner in leftover or []:
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
    pool = check_pool(args.pool)
    pid_file, log_file, config_file = files(repo, pool)
    pid = alive(pid_file)
    config = json.loads(config_file.read_text()) if config_file.exists() else {}
    print(f'Supervisor: {"running, pid " + str(pid) if pid else "not running"}'
          + (f'; keeps {config["count"]} ready; log {log_file}' if config else ''))
    remote = {r['name']: r for r in remote_runners(repo, config.get('prefix', 'jfactory-')) or []}
    for name, state in sorted(containers(repo, pool).items()):
        r = remote.get(name)
        print(f'{name}\tcontainer {state}\t' + (f'GitHub {r["status"]}{" busy" if r["busy"] else " idle"}'
                                                  if r else 'GitHub not yet listed'))
    return 0


def default_count():
    """Half the CPUs, but at most one runner per 6 GB: type checks and test runners for a real app need 4 GB or more
    each, and runners without a memory limit that outgrow the machine get killed mid-job."""
    cpus = max(1, (os.cpu_count() or 2) // 2)
    try:
        memory_gb = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES') / 2 ** 30
    except (ValueError, OSError, AttributeError):
        return cpus
    return max(1, min(cpus, int(memory_gb // 6)))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = p.add_subparsers(dest='command', required=True)
    up = sub.add_parser('up', help='Build the image if needed and start the supervisor that keeps runners ready')
    up.add_argument('--pool', default='', help='A separate pool on this machine, such as deploy (label jfactory-<pool>, no shared cache)')
    up.add_argument('--repo', help='owner/name; defaults to the current checkout')
    up.add_argument('--count', type=int, default=default_count(),
                    help='Runners kept ready for jobs at once on this machine (default: half the CPUs, at most one '
                         'per 6 GB of memory)')
    up.add_argument('--labels', default='', help='Extra comma-separated labels after self-hosted and jfactory')
    up.add_argument('--host', help='Machine name used in runner names (default: hostname)')
    up.add_argument('--cpus', type=float, help='CPU limit per runner')
    up.add_argument('--cpu-range', help='CPUs this pool may use, such as 0-5; the rest stay free for other work '
                                        '(another pool, a UX loop). Default: every CPU')
    up.add_argument('--memory', help='Memory limit per runner, for example 6g; needs Docker with the cgroup memory controller')
    up.add_argument('--shm-size', default='2g', help='Shared memory per runner; browsers need more than the default')
    up.add_argument('--cache-dir', help='Host folder shared by this machine\'s runners as /cache, so jobs reuse Node, npm '
                                        'packages and browsers instead of downloading them (references/ci-runners.md)')
    up.add_argument('--pr-jobs', action='store_true', help='This pool runs only pull-request jobs, like the main pool, '
                                                             'so it may share --cache-dir (the light pool)')
    up.add_argument('--no-pin', action='store_true', help='Do not pin each runner to its own CPU slice; use with --cpus '
                                                            'for a pool of small jobs (references/ci-runners.md)')
    up.add_argument('--build', action='store_true', help='Rebuild the image even when it exists')
    up.add_argument('--pull', action='store_true', help='Pull the newest base image when building')
    serve = sub.add_parser('serve', help='The supervisor loop that `up` starts in the background')
    serve.add_argument('--pool', default='', help='A separate pool on this machine, such as deploy (label jfactory-<pool>, no shared cache)')
    serve.add_argument('--repo')
    serve.add_argument('--once', action='store_true', help='Reconcile once and exit')
    down = sub.add_parser('down', help="Stop the supervisor and remove this machine's runners for the repository")
    down.add_argument('--pool', default='', help='A separate pool on this machine, such as deploy (label jfactory-<pool>, no shared cache)')
    down.add_argument('--repo')
    down.add_argument('--wait', type=float, default=30, help='Minutes to wait for running jobs before giving up')
    down.add_argument('--force', action='store_true', help='Stop runners even in the middle of a job')
    status = sub.add_parser('status', help="Show the supervisor, this machine's runners and their GitHub state")
    status.add_argument('--pool', default='', help='A separate pool on this machine, such as deploy (label jfactory-<pool>, no shared cache)')
    status.add_argument('--repo')
    args = p.parse_args(argv)
    try:
        return {'up': cmd_up, 'serve': cmd_serve, 'down': cmd_down, 'status': cmd_status}[args.command](args)
    except Refused as exc:
        print(f'Refused: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
