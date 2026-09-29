# Set up and run production releases

Use during setup, when a repository's release path changes, and whenever the owner asks for a release. Keep the repository's actual procedure in `.jfactory/coordination.json` and its delivery docs, never inside the distributed skill.

jfactory's [default policy](auto-merge.md#default-policy-verified-work-merges-itself-production-does-not) has two halves. Verified work merges itself to staging at most, and production changes only when the owner asks. This reference covers the second half. Setup establishes the path to production. The agent follows it when asked, so the owner answers "release?" without reconstructing how.

## Choose a release path

A good path has four properties:

- **Merging cannot reach production traffic.** Merges build staging, or nothing.
- **Promotion ships what was checked.** Prefer promoting the build that ran on staging. Where the host can only rebuild, deploy the exact commit staging runs, never a newer head of the base branch.
- **The host enforces the owner's approval where it can.** Instructions tell the agent to wait for a request. A protected environment or promotion permission makes that true even when an agent misreads a message.
- **Rollback is one recorded step.** Name the command or dashboard action before the first release, not during an incident.

Common patterns, checked September 2026. Confirm current host documentation before configuring, and record what you configured.

| Host | Merge reaches | Release |
| --- | --- | --- |
| Vercel, custom environment (Pro and Enterprise) | A `staging` environment tracking the base branch, with its own domain and variables | Move the production branch forward, for example by merging the base into a `production` branch through a workflow. [Custom environments](https://vercel.com/docs/deployments/environments) keep staging credentials separate |
| Vercel, staged production (all plans) | With **Auto-assign Custom Production Domains** turned off (Settings → Environments → Production), a production build that serves no traffic | `vercel promote <deployment-url>` or **Promote** in the dashboard assigns domains without a rebuild. Rollback: `vercel rollback`. The staged build uses **production variables and data**, so checks against it must be read-only ([docs](https://vercel.com/docs/deployments/promoting-a-deployment)) |
| GitHub Actions, any cloud | A job deploys to a `staging` [environment](https://docs.github.com/en/actions/managing-workflow-runs-and-deployments/managing-deployments/managing-environments-for-deployment) on push to the base branch | A `workflow_dispatch` job targets a `production` environment with required reviewers, deployment limited to the base branch, and administrator bypass disallowed. Start from the [release workflow template](../templates/release-production.yml) |
| Tags or a release branch | The base branch deploys to staging | Pushing a `v*` tag, or fast-forwarding a `production` branch, deploys. Restrict who can create those refs with a tag or branch ruleset, and prefer adding a protected environment |

Other hosts often have an equivalent promote or publish action, such as pipeline promotion or locked auto-publishing. Use it when it promotes an existing build.

Plan limits matter. On GitHub Free, Pro and Team, environment required reviewers and the administrator-bypass setting work only in public repositories; private repositories need GitHub Enterprise ([docs](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)). Otherwise use an approval the release host enforces, such as a promotion permission or production credential the agent's identity lacks, and check the plan before relying on a tag or branch ruleset. If no enforced gate is available, record `approval` as an instruction-only gate and say so in the setup record. Do not upgrade a plan or change repository visibility to get the feature. If the agent triggers releases with the owner's own token, GitHub's "Prevent self-review" option blocks the owner from approving; use a separate agent identity or leave that option off.

Changing where merges deploy, creating environments and editing host settings need the owner's authorization and access. Prepare the exact change and owner steps when the agent cannot apply them. A library or tool that publishes packages follows the same rules: publishing is the release, and merging should not publish.

## Record the procedure

Add a `release` block beside `merge_deploys` in `.jfactory/coordination.json`:

```json
{
  "merge_deploys": "staging",
  "release": {
    "staging": "https://staging.example.com",
    "production": "https://example.com",
    "revision": "curl -s https://<host>/api/version, or the host's deployment list; prints the deployed commit",
    "promote": "gh workflow run release-production.yml -f sha=<staging commit>; the owner approves the production environment",
    "approval": "GitHub environment production requires @owner; admins cannot bypass",
    "rollback": "gh workflow run release-production.yml -f sha=<previous production commit>"
  }
}
```

`staging` is required when `merge_deploys` is `staging`. `production`, `revision`, `promote` and `rollback` are required whenever the block exists. Keep `approval` empty only when the host cannot enforce it, and say what the gate is instead. Commands can name a dashboard action when no command exists. Values are the repository's facts; replace every placeholder. Link the block from the agent instructions' merge/release policy.

`setup_check.py` fails when `merge_deploys` is `staging` and PR delivery is `verified` without a complete `release` block, and warns while delivery is still open. It also warns when `approval` is missing. It checks that the record exists and is filled in, not that the commands work. A first supervised release proves that.

The `revision` step is what makes a release checkable. If neither environment can report the commit it runs, add that first, for example a version endpoint or build metadata, through a normal PR.

## Release when the owner asks

A release request names production, such as "release", "ship it to production" or "promote staging". A merge, green checks, a verified verdict or a standing auto-merge authorization is never one. When the request is ambiguous, ask which revision and environment.

1. **Identify what ships.** Read the commit staging runs and the commit production runs with `revision`. Unless the owner named another commit, release what staging runs. Confirm it is on the base branch. List the merged PRs between the production and staging commits with `git log <production>..<staging>`.
2. **Check it on staging.** Each merged PR passed its own verification, but not the combination. Run the affected features' recipes against staging at that commit, and record `deployed` evidence with the [evidence runner](verification.md#optional-deterministic-receipts) or equivalent. A failure stops the release.
3. **Name irreversible steps.** Data migrations, provider changes, emails and anything else that rollback cannot undo get named to the owner before promoting, unless the owner already approved them for this release.
4. **Promote.** Run `promote`. When a protected environment waits for approval, tell the owner exactly what is waiting and where. Never bypass, re-route or self-approve the gate.
5. **Check production.** Confirm with `revision` that production runs the promoted commit. Run read-only checks there: the critical journey's non-mutating steps, health endpoints and error rates. Never run destructive tests, seeds or paid provider tasks against production. Record `deployed` evidence.
6. **Report.** Name the commit, the PRs it shipped, the approval, the production checks and any gaps.

If the production check fails and the release included no irreversible step, run `rollback` to the previous production commit, confirm it with `revision`, and report both. Otherwise stop and report, because a rollback might make the damage worse. The owner's request covers one release. It does not authorize later releases, and it is not a standing production permission.
