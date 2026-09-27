# Prepare the host and test environments

Use during adoption and when a task needs a new execution target. Keep the resulting map in the project's existing system map or runbook, never inside the distributed skill.

## Map what the test actually reaches

For each relevant local, preview, staging or production target, record the launch command/URL, source or deployed revision, auth tenant/test account, database, storage, workers/queues and real or mocked providers. Record isolation and cleanup ownership, required secret names without values, allowed side effects and any cost limits. Mark unknown connections explicitly. Do not assume a URL containing "preview" or "staging" makes data disposable.

| Target | What it means |
| --- | --- |
| Workspace preview | A route to a process running in the workspace; it does not deploy the app or isolate its dependencies |
| PR deployment preview | A hosted branch/commit build with its configured services and environment variables |
| Staging | A deliberately configured non-production environment, including its backing services and data |
| Production | The real customer environment, governed by the recorded release policy |

A PR preview can use staging services. A preview alone does not establish that those services are isolated. Verify the build identity before attributing results to the current PR. Follow the host's access rules for private previews and evidence. For Vercel, inspect its [environment configuration](https://vercel.com/docs/deployments/environments), including integrations outside the repository's CI.

Never run destructive seeds/migrations or paid provider tasks against an unknown target. Resolve the specific ambiguity and continue safe lower-scope work. Separate accounts, record namespaces, browser profiles and ports for concurrent tasks. Ref-based CI concurrency is insufficient when different branches write the same account or database. Isolate test data or serialize only the shared operation with a common lock/CI concurrency group.

## Bootstrap and diagnose

Prefer the repo's existing setup command. Make it repeatable in a fresh checkout: select the project's runtime, respect its lockfile, install dependencies and needed browser binaries, and explain prerequisites. It must not reset shared data or deploy as an incidental install step. Keep local-only paths and secrets out of committed scripts.

A doctor should give actionable results for missing runtimes/dependencies, configuration presence, service reachability and authentication readiness. Presence is not validated access. Give the command or owner action that addresses each gap, and use failure status when a required capability is unavailable. It should still describe other capabilities that work. Keep setup and diagnostic steps separable so resuming does not reinstall everything.

Distinguish a successful command in the current checkout from a proven fresh-host setup. Record what ran, where, and what has only been prepared. A shell script checked into Git does not register itself with a workspace manager.

## Conductor local and cloud

Read the available Conductor skill, inspect `CONDUCTOR_IS_LOCAL` and current CLI help, and consult current official host documentation before changing configuration. Local worktrees and cloud workspaces have different setup mechanisms. Do not infer cloud behavior from a Mac configuration file.

According to [Conductor's Cloud Computer documentation](https://www.conductor.build/docs/cloud/cloud-computer), checked September 2026:

- A cloud workspace has its own microVM. The active Cloud Computer build supplies its base environment; existing workspaces retain their earlier environment.
- Cloud's per-repository Setup script is configured in organization settings or an Admin workspace. It runs for each new workspace. Cloud does not consume the setup script in `.conductor/settings.toml` or `conductor.json`.
- A versioned repository bootstrap command can be called by both local setup configuration and the cloud Setup script. Shared software installation belongs in the Cloud Computer build when appropriate.
- Admin tools can configure setup scripts/builds, but the owner manages saved secrets and repository membership in settings.

Check the current docs if these details differ from the bundled host instructions. Configure authorized host settings when the available tools permit it. Otherwise prepare the exact bootstrap command and tell the owner where to register it. Report "script prepared; cloud registration pending" until confirmed. Do not claim a new workspace will bootstrap merely because a local setup file was committed. Explain which changes need a new build/workspace to take effect.

For a required signed-in browser, use the [UX access handoff](../skills/jfactory-ux/SKILL.md). Prepare the supported browser, give the owner its authenticated access link or local window, pause browser interaction for sign-in, then validate access after control returns. A new workspace or expired profile may require a new login. Never assume access to the owner's Mac from cloud.
