# CI on machines you own

GitHub-hosted runners bill private repositories by the minute, and when the account's spending limit is reached GitHub refuses every job before it starts. Required checks then fail in seconds for every PR, which looks like broken code but is billing. Running the checks on machines you own avoids both: self-hosted runners cost no Actions minutes.

Required checks still have to come from GitHub Actions. A ruleset accepts `jfactory verified` and the CI gate only from the GitHub Actions app, so a status posted by an agent or a local script does not count. What moves is where the jobs run, not who reports them.

## How it works

- Each jfactory workflow template picks its runner from the `JFACTORY_RUNNER` repository variable, a JSON value: `runs-on: ${{ fromJSON(vars.JFACTORY_RUNNER || '"ubuntu-latest"') }}`. Unset, jobs run on GitHub's `ubuntu-latest`. Set it to `["self-hosted","jfactory"]` and they run on your runners. One variable switches every job back and forth, without a PR.
- `scripts/runners.py up` starts runners on a machine as Docker containers. The image is GitHub's runner image (Ubuntu) plus `gh`, `python3`, `jq` and `zip`, with passwordless sudo so steps like `playwright install --with-deps` work. `actions/setup-node`, `actions/setup-python` and caches work as on hosted runners. Containers restart with Docker and keep their registration, so a machine that reboots rejoins on its own.
- Any machine with Docker can run them: a cloud VM, a workstation or a Mac (Docker Desktop runs the Linux image). Runners from several machines share one queue; GitHub sends each job to the next idle runner with the right labels.
- Production releases stay on GitHub-hosted runners (`templates/release-production.yml` does not read the variable), so a release never depends on whether one of your machines is up.

## Set it up

1. **Access.** Registering a runner needs a token that can administer the repository's runners: `gh` signed in as a repository admin, or `GH_TOKEN` set to a fine-grained token limited to the repository with "Administration: read and write" (add "Variables: read and write" to set the variable from the command line). GitHub App tokens without that permission, such as some agent hosts' tokens, get HTTP 403; the owner creates the token, and it is never committed or put in a command line.
2. **Start runners** on each machine, from the repository checkout:
   ```bash
   python3 .agents/skills/jfactory/scripts/runners.py up --count 4
   python3 .agents/skills/jfactory/scripts/runners.py status
   ```
   The default count is half the machine's CPUs. Give browser jobs room: `--memory 6g` caps each runner, and `--shm-size` (default `2g`) is the shared memory Chromium needs.
3. **Route the jobs** once at least one runner shows `online`: `gh variable set JFACTORY_RUNNER --body '["self-hosted","jfactory"]'`, or Settings > Secrets and variables > Actions > Variables.
4. **Prove it** with a PR whose checks run on the runners: the job log's "Set up job" step names the runner. Record the result in the setup record.

Project workflows that are not jfactory templates (for example the project's own browser suite) can read the same variable in their `runs-on`, so one switch moves the whole PR gate. Keep deploy and production jobs on hosted runners unless the owner decides otherwise.

## Keep it healthy

- **No runner online means jobs wait**, up to 24 hours, then fail. If the machines go away, unset the variable (`gh variable delete JFACTORY_RUNNER`) and jobs return to GitHub's runners. Report runner capacity as a delivery blocker; never bypass the gate instead.
- **Stop runners** with `runners.py down`, which unregisters them; GitHub also drops runners that stay offline for 14 days.
- **Public repositories:** do not route `pull_request` jobs from forks to self-hosted runners. A fork's PR could run its code on your machine. Public repositories get hosted minutes free, so keep them on GitHub's runners.
- **Isolation:** a runner container keeps its workspace and caches between jobs, as a long-lived runner does. Checkout cleans the tree, but treat the machine as trusted for the repository's own branches only, and keep secrets in GitHub, not on the machine.
