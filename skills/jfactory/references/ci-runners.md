# CI on machines you own

GitHub-hosted runners bill private repositories by the minute. When the account's spending limit is reached, GitHub refuses every job before it starts, so required checks fail in seconds on every PR. That looks like broken code, but it's billing. Running the checks on machines you own avoids both problems: self-hosted runners cost no Actions minutes.

Required checks still have to come from GitHub Actions. A ruleset accepts `jfactory verified` and the CI gate only from the GitHub Actions app, so a status posted by an agent or a local script doesn't count. What moves is where the jobs run, not who reports them.

## How it works

- **One variable picks the runner.** Each jfactory workflow template reads the `JFACTORY_RUNNER` repository variable, a JSON value: `runs-on: ${{ fromJSON(github.event.pull_request.head.repo.fork && '"ubuntu-latest"' || vars.JFACTORY_RUNNER || '"ubuntu-latest"') }}`. Unset, jobs run on GitHub's `ubuntu-latest`. Set to `["self-hosted","jfactory"]`, they run on your runners. Fork PRs always run on GitHub's runners, whatever the variable says. Switching back and forth needs no PR.
- **Every job gets a fresh container.** It runs that one job and is then deleted, as on hosted runners, so nothing one job leaves behind (a modified tool, a background process, a credential) reaches a later job or the `jfactory verified` gate.
- **A supervisor keeps runners ready.** `scripts/runners.py up` starts it on the host. It keeps `--count` runners waiting: for each, it asks GitHub for a single-use runner configuration and copies it into a new container, never as an argument or environment variable. The admin token stays on the host; a container only ever sees its own single-use configuration.
- **The image** is GitHub's runner image (Ubuntu) plus `gh`, `python3`, `jq`, `zip`, the system libraries Playwright's Chromium needs, and passwordless sudo for `apt-get` steps. `actions/setup-node`, `actions/setup-python` and `actions/cache` work as on hosted runners.
  - It doesn't have everything hosted runners preinstall: no Docker daemon, so no `services:` or container jobs, no other browsers' libraries, and no language toolchains beyond what setup actions download. A step that assumes one of those needs an install step or an image addition.
  - Fresh containers start with empty tool caches. Restore dependencies with `actions/cache`, or share a cache on the machine ([warm runners](#warm-runners-share-a-cache-on-the-machine)).
- **Any machine with Docker can run them:** a cloud VM, a workstation or a Mac with Docker Desktop. Runners from several machines share one queue.
  - On Apple Silicon the runners are `arm64`, while GitHub's runners are `x64`, so include `${{ runner.arch }}` in cache keys for anything with native binaries (such as `node_modules`).
- **Production releases stay on GitHub-hosted runners.** `templates/release-production.yml` doesn't read the variable, so a release never depends on whether one of your machines is up.

## Set it up

1. **Access.** The supervisor needs a token that can administer the repository's runners: `gh` signed in as a repository admin, or `GH_TOKEN` set to a fine-grained token limited to the repository with "Administration: read and write". Add "Variables: read and write" to set the variable from the command line.
   - GitHub App tokens without that permission get HTTP 403. Some agent hosts wrap `gh` and swap in their own token, so call the real `gh` binary.
   - The owner creates the token. It is never committed or put on a command line.
2. **Start the supervisor** on each machine, from the repository checkout:
   ```bash
   python3 .agents/skills/jfactory/scripts/runners.py up --count 4 --memory 6g
   python3 .agents/skills/jfactory/scripts/runners.py status
   ```
   - The default count is half the machine's CPUs, but at most one runner per 6 GB of memory. Real type checks and test runners need 4 GB or more each, and runners that outgrow the machine get killed mid-job (the log says `Killed`). Add swap as a margin.
   - Each runner is pinned to its own share of the CPUs. Test runners such as Vitest and Jest start one worker per CPU they can see, and an unpinned container sees the whole machine: one Loopcraft unit-test job on an 8-CPU VM started 9 processes using 3.7 GB, where a 2-CPU hosted runner starts a few. Pinning makes each job size itself like a hosted runner with the same CPUs.
   - `--memory` caps each runner, but only where Docker has the cgroup memory controller (some sandboxed VMs refuse it, and every container then fails to start). `--shm-size` (default `2g`) is the shared memory Chromium needs.
   - The supervisor logs to `~/.cache/jfactory-runners/` and doesn't survive a reboot. Run `up` again, or start it from the machine's service manager.
3. **Route the jobs** once runners show `online`: `gh variable set JFACTORY_RUNNER --body '["self-hosted","jfactory"]'`, or Settings > Secrets and variables > Actions > Variables.
4. **Prove it** with a PR whose checks run on the runners: the job log's "Set up job" step names the runner. Record the result in the setup record.

Project workflows that aren't jfactory templates (for example the project's own browser suite) can use the same `runs-on` expression, so one switch moves the whole PR gate. Keep deploy and production jobs on hosted runners unless the owner decides otherwise.

## Warm runners: share a cache on the machine

A fresh container downloads everything again: Node, npm packages and browsers. On a busy repository that costs one to two minutes per job. `up --cache-dir PATH` gives the machine's runners one shared cache folder for downloads. The setting is stored in the supervisor's config file (`cache_dir`).

- **What is shared.** Each runner container mounts the folder at `/cache` and gets these variables:
  - `RUNNER_TOOL_CACHE=/cache/toolcache`: `actions/setup-node` and other setup actions reuse the tools they downloaded.
  - `npm_config_cache=/cache/npm`: npm reuses downloaded packages.
  - `PLAYWRIGHT_BROWSERS_PATH=/cache/ms-playwright`: Playwright finds installed browsers.
  - `JFACTORY_RUNNER_CACHE=/cache`: workflows test this variable to use the cache for more, for example a saved `node_modules` per lockfile or a build cache. Keep the hosted steps for runs where the variable is empty.
- **The supervisor prepares the folder.** It creates the subfolders and gives them to the image's `runner` user. It uses a short container for this, so it needs no root on the host.
- **Workspaces stay fresh.** Only `/cache` is shared. Each job still gets a new container with its own checkout, home folder and processes. The container is deleted after its one job.
- **Risk: a shared, writable cache.** Any job on the machine can write to it. A bad branch, or a compromised npm package in an ordinary PR, could leave a changed tool, package or browser that a later job uses. For PR checks this is acceptable because these runners take trusted branches from the same repository. Fork PRs always run on GitHub's runners. Don't share a cache between repositories with different trust.
- **Never let deploy jobs use it.** A deploy or release job holds production secrets. If it ran a tool a PR job had changed in the cache, that PR would reach production. Run deploy jobs in a [separate pool](#deploy-jobs-a-separate-pool-without-the-cache).
- **Clear it** when you suspect a bad entry or the disk fills: `sudo rm -rf PATH`. The files belong to the container's `runner` user, so this needs root. The supervisor makes the folder again before it starts the next runner, and jobs download again. Do it when no job is running, or a running job may fail.

## Deploy jobs: a separate pool without the cache

Deploys, releases and other jobs with production secrets run on their own pool on the same machine:

```bash
python3 scripts/runners.py up --pool deploy --count 1 --memory 4g     # label jfactory-deploy, no shared cache
gh variable set JFACTORY_DEPLOY_RUNNER --body '["self-hosted","jfactory-deploy"]'
```

- **Its own label.** Pool runners carry only `jfactory-<pool>`, so PR jobs asking for `jfactory` never land on them.
- **No shared cache.** `up` refuses `--cache-dir` with `--pool`. Every deploy job downloads its tools fresh in a new container.
- **Its own settings.** The pool keeps its own config, log and pid files (`<owner>__<repo>--<pool>.*`) and counts only its own containers. Run it as a second supervisor service, and pass `--pool` to `status` and `down` too.
- **Route the jobs.** Deploy workflows use `runs-on: ${{ fromJSON(vars.JFACTORY_DEPLOY_RUNNER || '"ubuntu-latest"') }}`, as in the release template. With the variable unset, they stay on GitHub's runners.

## Small jobs: a light pool

Gates, planners and jobs that only wait for another service (a preview deploy that polls Vercel) take seconds of CPU. On a shared pool they still wait for a free runner, behind suites that run for 20 minutes or more. Give them their own small pool on the same machine:

```bash
python3 scripts/runners.py up --pool light --pr-jobs --no-pin --cpus 1 --memory 2g --count 3 --cache-dir /home/ci/runner-cache
gh variable set JFACTORY_LIGHT_RUNNER --body '["self-hosted","jfactory-light"]'
```

- **Same trust as the main pool.** It runs pull-request jobs only, so it may share the cache folder (`--pr-jobs`). The deploy pool never takes `--pr-jobs`.
- **No CPU slice.** `--no-pin` with `--cpus 1` lets small jobs use any CPU for a moment instead of taking a slice from the long jobs.
- **Route only small jobs.** Use `vars.JFACTORY_LIGHT_RUNNER || vars.JFACTORY_RUNNER || '"ubuntu-latest"'` for gates (the required aggregate job), planners, credential probes and deploy polling. Never route tests or builds to it. With the variable unset, the jobs use the main pool.

## Queue operations: fewer jobs before more machines

The PR rate stays about the same, and the machine is fixed. Queue time falls only when jobs fall or each job gets cheaper. Work through these in order, and measure the queue after each (`started_at` minus `created_at` per job):

1. **Do not start runs that will go stale.** With "require branches to be up to date", bring ONE verified PR up to date at a time, oldest first, and only when no other verified PR is still running CI or waiting to merge (a merge train). Updating every behind PR after each merge starts N full runs for one merge slot, and all but one go stale at the next merge. `auto_merge.py` and `pr_health.py` follow this rule.
2. **Do not restart runs for events that change nothing.** Labels, comments and title edits must not trigger the test workflow. Read labels such as `full-suite` live in the planner, and re-run after adding one.
3. **Push once per batch.** Each push to a PR cancels its run and joins the back of the queue ([CI confirms](delivery.md#ci-confirms-it-does-not-discover)).
4. **Keep small jobs off the big runners** (the light pool above).
5. **Use every CPU.** Each runner gets its own CPU slice. `runners.py` picks the least-used slot among live containers, so two jobs never share a slice while another slice sits idle.
6. **Fix a red base branch first.** Failing tests wait for their timeouts, often minutes each and on every viewport. On a red base branch every PR pays that cost again.
7. **Make each job cheaper:** related tests only, one build per run when there are several browser jobs, fewer duplicate viewport runs, and faster test fixtures. Measure before and after.
8. **Cap the workers, not just the work.** Each program has its own concurrency limit, but all programs share one queue. Set `repo_limit` in `.jfactory/coordination.json` to about the number of main runners; `coord.py launch` refuses beyond it.
9. **Debounce pushes.** The first job of a PR run waits about a minute on the light pool before any big job starts, so a quick second push cancels the run cheaply.
10. **Watch the queue.** The stuck-PR check reports the number of waiting runs and the oldest wait, and keeps its issue open while the oldest wait is 30 minutes or more.
11. **Then add machines.**

## Keep it healthy

- **One slot per runner, and room for other work.** Each runner gets its own CPUs. A runner that starts while a finished container is still being removed takes the least-used slot, never a busy one (fixed after two runners shared CPUs 0-1 while 6-7 sat idle). When the same machine also runs other work, such as a UX loop or a deploy pool, give each its own CPUs: `up --cpu-range 0-5` keeps the pool on CPUs 0-5, and the other service is pinned to the rest (for systemd, `AllowedCPUs=6-7`). On machines with two threads per core, 2 CPUs is one physical core per job.
- **Match jobs to runners.** Queue time grows when the jobs waiting exceed the runners. Count jobs per PR times the PRs that push at the same time. If that is many times the runner count, jobs wait longer than they run. Before you add machines: run small changes' static checks (types, lint, related unit tests) in one job, keep the program's concurrency limit, and have agents check before they push ([CI confirms](delivery.md#ci-confirms-it-does-not-discover)). Compare each job's `started_at` with its `created_at` to measure the wait.

- **No runner online means jobs wait** up to 24 hours, then fail. If the machines go away, delete the variable (`gh variable delete JFACTORY_RUNNER`) and jobs return to GitHub's runners. Report runner capacity as a delivery blocker; never bypass the gate instead.
- **Stop with `runners.py down`.** It stops the supervisor, waits up to `--wait` minutes (default 30) for running jobs to finish, then removes the containers and their GitHub registrations. `--force` stops jobs midway. It exits non-zero and names anything it couldn't remove.
- **Public repositories:** the expression already keeps fork PRs on GitHub's runners. Public repositories get hosted minutes free, so leave them there unless there's a reason not to.
- **Trust.** Containers are isolated from each other and from the host's Docker, but a job runs with root inside its own container. Use these runners for repositories whose branches you trust, and keep secrets in GitHub, not on the machine.
