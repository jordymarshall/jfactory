#!/usr/bin/env python3
"""Run a repository's CI on machines you own: start, list and stop Docker-based GitHub Actions runners.

Each runner is a container built from GitHub's runner image plus the tools hosted Ubuntu runners provide that CI
steps commonly call (gh, python3, jq, zip), with passwordless sudo so `apt-get` steps such as
`playwright install --with-deps` work. Containers restart with Docker and keep their registration, so a machine
that reboots rejoins without a new token. Workflows choose these runners through the `JFACTORY_RUNNER` repository
variable (references/ci-runners.md); this script never changes workflows or repository settings.

Registering needs a token that can administer the repository's runners: `gh` signed in as a repository admin, or
GH_TOKEN set to a fine-grained token with "Administration: read and write" on that repository. GitHub App tokens
without that permission get HTTP 403.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

IMAGE = 'jfactory-runner:latest'
LABEL = 'jfactory'
# The container label that marks containers this script owns, so `down` never touches anything else.
OWNER_LABEL = 'jfactory.runner'
DOCKERFILE = r'''FROM ghcr.io/actions/actions-runner:latest
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git gnupg jq python3 python3-venv unzip xz-utils zip \
 && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o /usr/share/keyrings/githubcli.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list \
 && apt-get update && apt-get install -y --no-install-recommends gh \
 && rm -rf /var/lib/apt/lists/*
COPY entrypoint.sh /entrypoint.sh
RUN chmod 755 /entrypoint.sh
USER runner
ENTRYPOINT ["/entrypoint.sh"]
'''
# Registers once; a restarted container reuses its saved registration instead of needing a fresh token.
ENTRYPOINT = r'''#!/bin/bash
set -euo pipefail
cd /home/runner
if [ ! -f .runner ]; then
  ./config.sh --unattended --replace --url "https://github.com/$RUNNER_REPO" --token "$RUNNER_TOKEN" \
    --name "$RUNNER_NAME" --labels "$RUNNER_LABELS" --work _work
fi
unset RUNNER_TOKEN
exec ./run.sh
'''


class Refused(Exception):
    pass


def run(cmd, check=True, capture=True, input=None):
    result = subprocess.run(cmd, capture_output=capture, text=True, input=input)
    if check and result.returncode:
        detail = (result.stderr or result.stdout or '').strip() if capture else ''
        raise Refused(f'{" ".join(cmd[:3])} failed: {detail}' if detail else f'{" ".join(cmd[:3])} failed')
    return result


def need(tool):
    if not shutil.which(tool):
        raise Refused(f'`{tool}` is not installed; references/ci-runners.md lists what each machine needs')


def docker(*args, **kw):
    return run(['docker', *args], **kw)


def repo_slug(value):
    if value:
        slug = value
    else:
        slug = run(['gh', 'repo', 'view', '--json', 'nameWithOwner', '-q', '.nameWithOwner']).stdout.strip()
    if not re.fullmatch(r'[\w.-]+/[\w.-]+', slug or ''):
        raise Refused(f'Cannot tell the repository from {slug!r}; pass --repo owner/name')
    return slug


def token(repo, kind):
    """A short-lived registration or removal token; 403 means the signed-in token cannot administer runners."""
    result = run(['gh', 'api', '-X', 'POST', f'repos/{repo}/actions/runners/{kind}-token', '-q', '.token'], check=False)
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        hint = (' The signed-in token cannot administer runners: sign `gh` in as a repository admin or set GH_TOKEN to a'
                ' fine-grained token with "Administration: read and write" on this repository.') \
            if '403' in detail or 'not accessible' in detail else ''
        raise Refused(f'GitHub refused a runner {kind} token for {repo}: {detail}.{hint}')
    return result.stdout.strip()


def owned(repo=None):
    """This script's containers, optionally for one repository: [(name, state, repo)]."""
    fmt = '{{.Names}}\t{{.State}}\t{{.Label "' + OWNER_LABEL + '"}}'
    out = docker('ps', '-a', '--filter', f'label={OWNER_LABEL}', '--format', fmt).stdout
    rows = [tuple(line.split('\t')) for line in out.splitlines() if line.strip()]
    return [r for r in rows if repo is None or r[2] == repo]


def container_name(repo, host, index):
    base = re.sub(r'[^a-z0-9-]+', '-', f'{repo.split("/")[1]}-{host}'.lower()).strip('-')
    return f'jfactory-runner-{base}-{index}'


def build(pull):
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, 'Dockerfile'), 'w') as f:
            f.write(DOCKERFILE)
        with open(os.path.join(tmp, 'entrypoint.sh'), 'w') as f:
            f.write(ENTRYPOINT)
        docker('build', *(['--pull'] if pull else []), '-t', IMAGE, tmp, capture=False)


def cmd_up(args):
    need('docker')
    need('gh')
    repo = repo_slug(args.repo)
    if args.count < 1:
        raise Refused('--count must be at least 1')
    labels = ','.join(dict.fromkeys([LABEL, *[x.strip() for x in args.labels.split(',') if x.strip()]]))
    host = args.host or os.uname().nodename.split('.')[0]
    if args.build or not docker('image', 'inspect', IMAGE, check=False).returncode == 0:
        build(args.pull)
    existing = {name: state for name, state, _ in owned(repo)}
    started = []
    reg = None
    for i in range(1, args.count + 1):
        name = container_name(repo, host, i)
        if name in existing:
            if existing[name] != 'running':
                docker('start', name)
            continue
        reg = reg or token(repo, 'registration')
        cmd = ['run', '-d', '--name', name, '--restart', 'unless-stopped', '--label', f'{OWNER_LABEL}={repo}',
               '-e', f'RUNNER_REPO={repo}', '-e', f'RUNNER_NAME={name}', '-e', f'RUNNER_LABELS={labels}',
               '-e', 'RUNNER_TOKEN', '--shm-size', args.shm_size]
        if args.cpus:
            cmd += ['--cpus', str(args.cpus)]
        if args.memory:
            cmd += ['--memory', args.memory]
        # The token goes through the environment, never the command line or process list.
        subprocess.run(['docker', *cmd, IMAGE], check=True, capture_output=True, text=True,
                       env={**os.environ, 'RUNNER_TOKEN': reg})
        started.append(name)
    print(f'{len(started)} started, {args.count - len(started)} already present for {repo} with labels {labels}.')
    print(f'Route workflows here with the repository variable JFACTORY_RUNNER={json.dumps(["self-hosted", LABEL])}.')
    return 0


def cmd_down(args):
    need('docker')
    repo = repo_slug(args.repo)
    rows = owned(repo)
    if not rows:
        print(f'No jfactory runners for {repo} on this machine.')
        return 0
    removal = None
    for name, state, _ in rows:
        if state != 'running':
            docker('start', name, check=False)
        try:
            removal = removal or token(repo, 'remove')
            subprocess.run(['docker', 'exec', '-e', 'RUNNER_REMOVE_TOKEN', name, 'bash', '-c',
                            'cd /home/runner && ./config.sh remove --token "$RUNNER_REMOVE_TOKEN"'],
                           capture_output=True, text=True, env={**os.environ, 'RUNNER_REMOVE_TOKEN': removal})
        except Refused as exc:
            # The container still goes; GitHub drops an offline runner on its own after 14 days.
            print(f'Check: {exc} {name} stays listed on GitHub until removed there.', file=sys.stderr)
        docker('rm', '-f', name)
    print(f'Removed {len(rows)} runner(s) for {repo}.')
    return 0


def cmd_status(args):
    need('docker')
    repo = repo_slug(args.repo) if args.repo or not args.all else None
    rows = owned(repo)
    local = {name: state for name, state, _ in rows}
    remote = {}
    if repo and shutil.which('gh'):
        result = run(['gh', 'api', f'repos/{repo}/actions/runners', '--paginate', '-q',
                      '.runners[] | [.name, .status, (.busy|tostring)] | @tsv'], check=False)
        if result.returncode == 0:
            remote = {n: (s, b) for n, s, b in (line.split('\t') for line in result.stdout.splitlines() if line)}
    for name, state in sorted(local.items()):
        github = remote.get(name)
        print(f'{name}\tcontainer {state}\t' + (f'GitHub {github[0]}{" busy" if github[1] == "true" else ""}'
                                                  if github else 'GitHub unknown'))
    if not local:
        print('No jfactory runners on this machine.')
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = p.add_subparsers(dest='command', required=True)
    up = sub.add_parser('up', help='Build the image if needed and start runners registered to the repository')
    up.add_argument('--repo', help='owner/name; defaults to the current checkout')
    up.add_argument('--count', type=int, default=max(1, (os.cpu_count() or 2) // 2),
                    help='Runners on this machine (default: half the CPUs)')
    up.add_argument('--labels', default='', help='Extra comma-separated labels after self-hosted and jfactory')
    up.add_argument('--host', help='Machine name used in runner names (default: hostname)')
    up.add_argument('--cpus', type=float, help='CPU limit per runner')
    up.add_argument('--memory', help='Memory limit per runner, for example 6g')
    up.add_argument('--shm-size', default='2g', help='Shared memory per runner; browsers need more than the default')
    up.add_argument('--build', action='store_true', help='Rebuild the image even when it exists')
    up.add_argument('--pull', action='store_true', help='Pull the newest base image when building')
    down = sub.add_parser('down', help="Unregister and remove this machine's runners for the repository")
    down.add_argument('--repo')
    status = sub.add_parser('status', help="List this machine's runners and their GitHub state")
    status.add_argument('--repo')
    status.add_argument('--all', action='store_true', help='Every repository on this machine')
    args = p.parse_args(argv)
    try:
        return {'up': cmd_up, 'down': cmd_down, 'status': cmd_status}[args.command](args)
    except Refused as exc:
        print(f'Refused: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
