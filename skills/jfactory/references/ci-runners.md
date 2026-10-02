# CI on machines you own

GitHub-hosted runners bill private repositories by the minute. When the account's spending limit is reached, GitHub refuses every job before it starts, so required checks fail in seconds on every PR. That looks like broken code, but it's billing. Running the checks on machines you own avoids both problems: self-hosted runners cost no Actions minutes.

Required checks still have to come from GitHub Actions. A ruleset accepts `jfactory verified` and the CI gate only from the GitHub Actions app, so a status posted by an agent or a local script doesn't count. What moves is where the jobs run, not who reports them.

## How it works

- **One variable picks the runner.** Each jfactory workflow template reads the `JFACTORY_RUNNER` repository variable, a JSON value: `runs-on: ${{ fromJSON(github.event.pull_request.head.repo.fork && '"ubuntu-latest"' || vars.JFACTORY_RUNNER || '"ubuntu-latest"') }}`. Unset, jobs run on GitHub's `ubuntu-latest`. Set to `["self-hosted","jfactory"]`, they run on your runners. Fork PRs always run on GitHub's runners, whatever the variable says. Switching back and forth needs no PR.
- **Every job gets a fresh container.** It runs that one job and is then deleted, as on hosted runners, so nothing one job leaves behind (a modified tool, a background process, a credential) reaches a later job or the `jfactory verified` gate.
- **A supervisor keeps runners ready.** `scripts/runners.py up` starts it on the host. It keeps `--count` runners waiting: for each, it asks GitHub for a single-use runner configuration and copies it into a new container, never as an argument or environment variable. The admin token stays on the host; a container only ever sees its own single-use configuration.
- **The image** is GitHub's runner image (Ubuntu) plus `gh`, `python3`, `jq`, `zip`, the system libraries Playwright's Chromium needs, and passwordless sudo for `apt-get` steps. `actions/setup-node`, `actions/setup-python` and `actions/cache` work as on hosted runners.
  - It doesn't have everything hosted runners preinstall: no Docker daemon, so no `services:` or container jobs, no other browsers' libraries, and no language toolchains beyond what setup actions download. A step that assumes one of those needs an install step or an image addition.
  - Fresh containers start with empty tool caches, so restore dependencies with `actions/cache`.
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
   - `--memory` caps each runner, but only where Docker has the cgroup memory controller (some sandboxed VMs refuse it, and every container then fails to start). `--shm-size` (default `2g`) is the shared memory Chromium needs.
   - The supervisor logs to `~/.cache/jfactory-runners/` and doesn't survive a reboot. Run `up` again, or start it from the machine's service manager.
3. **Route the jobs** once runners show `online`: `gh variable set JFACTORY_RUNNER --body '["self-hosted","jfactory"]'`, or Settings > Secrets and variables > Actions > Variables.
4. **Prove it** with a PR whose checks run on the runners: the job log's "Set up job" step names the runner. Record the result in the setup record.

Project workflows that aren't jfactory templates (for example the project's own browser suite) can use the same `runs-on` expression, so one switch moves the whole PR gate. Keep deploy and production jobs on hosted runners unless the owner decides otherwise.

## Keep it healthy

- **No runner online means jobs wait** up to 24 hours, then fail. If the machines go away, delete the variable (`gh variable delete JFACTORY_RUNNER`) and jobs return to GitHub's runners. Report runner capacity as a delivery blocker; never bypass the gate instead.
- **Stop with `runners.py down`.** It stops the supervisor, waits up to `--wait` minutes (default 30) for running jobs to finish, then removes the containers and their GitHub registrations. `--force` stops jobs midway. It exits non-zero and names anything it couldn't remove.
- **Public repositories:** the expression already keeps fork PRs on GitHub's runners. Public repositories get hosted minutes free, so leave them there unless there's a reason not to.
- **Trust.** Containers are isolated from each other and from the host's Docker, but a job runs with root inside its own container. Use these runners for repositories whose branches you trust, and keep secrets in GitHub, not on the machine.
