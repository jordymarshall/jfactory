# Set up and use protected auto-merge

The default delivery preference is a non-draft PR followed by auto-merge once verification is complete. Honor the target repository's owner-approved policy. A standing authorization covers subsequent in-scope PRs; do not ask again each time. Merely installing this skill in another owner's repository does not grant merge or production permissions.

## Default policy: verified work merges itself, production does not

This is jfactory's default unless the owner records otherwise:

- **Verified means the agreed standard passed.** Before implementation, each objective records its acceptance criteria and the evidence scopes each criterion requires (see the [verification contract](verification.md)). The agent works until every criterion passes at those scopes on the PR's current head. For application criteria, use the PR preview or staging, not production. Then it queues auto-merge without asking again. Missing, failed or stale proof keeps the PR open. Never weaken the standard to reach a merge.
- **Merging deploys at most to staging.** The base branch should deploy to a staging target, or nowhere. If merging currently releases production, auto-merge stays off until the release path is reconfigured, with the owner's authorization, so merges reach staging or nothing. There is no auto-merge exception for merge-to-production.
- **Production is a deliberate owner action.** Release to production only when the owner asks for that release. A merge, green CI, a verified verdict or a standing auto-merge authorization is not a production request. Record the manual release command or procedure in the repository's delivery docs.

## Establish the repository gates once

Inspect the repository's actual settings, branch protection/rulesets, required reviews, merge strategy and release triggers. The owner must know whether merging also deploys. Record that policy, and what merging deploys (`staging`, `none` or `production`), with the existing repository instructions and in `.jfactory/coordination.json` as `merge_deploys`. An existing auto-deploy pipeline is not separate evidence of release authorization. When authorization covers auto-merge but excludes its deployment side effect, resolve that conflict before enabling it.

On GitHub, enable **Allow auto-merge** under Settings → General → Pull Requests. On the target branch, require a PR, the change-aware CI aggregate check and the `jfactory verified` status from the [verification contract](verification.md#change-aware-verification-and-the-merge-gate). Do not require a fixed expensive suite for every change; the plan decides which suites a PR needs, and unknown files still require all of them. Prefer checks against the latest base or a supported merge queue for concurrent PRs. Preserve existing required reviews and protections; do not remove them to make automation faster. Configure these settings when the owner authorizes auto-merge setup and credentials permit it. If settings are inaccessible, describe the exact missing permission or plan feature. Do not change repository visibility or purchase a plan as a workaround.

Prefer squash merging when the repository has no established alternative. Keep shared task branches current by merging the base into them; use rebasing only when branch ownership and policy permit rewriting history. After any update, refresh affected proof before re-enabling auto-merge. Native auto-merge waits for gates; it does not itself maintain stale branches or start another agent session.

Consumer applications must select their own meaningful checks. A tooling repository might require a single integrity/test job; an application may also require browser, storage or provider checks. A workflow existing or passing once does not prove it is a required merge gate. A human screenshot of settings or an authoritative API response can establish settings when the agent cannot read them directly, but an unsupported assumption cannot.

A required check must fail when its mandatory work is missing. GitHub can accept a skipped job as a successful required status, so use an unconditional aggregate check that rejects failed, cancelled or skipped dependencies where those dependencies are required. Give narrower manual diagnostic runs a different check name so they cannot satisfy a full-suite gate. Shared test accounts/data require isolation or common concurrency control across branches, not only a per-branch lock.

## Enable it per PR

1. Review the actual diff and evidence at the current head. Complete required application/provider proof and owner decisions outside CI. Do not queue a PR with missing behavioral proof merely because its unit tests passed.
2. Confirm the intended base, permitted merge method, no unresolved failures or changes requested, and no unresolved dependency or conflict. Pending required CI is allowed only when the server enforces those exact checks. Refresh overlapping branches and verify combined behavior as described in [worktree coordination](worktrees.md).
3. Confirm merging reaches staging or nothing, per the default policy above.
4. With a protected target and squash permitted, use `gh pr merge <number> --auto --squash --match-head-commit <verified-head-sha>`. Use the repository's configured merge method or merge queue when different. Never use `--admin`. The command can merge immediately if requirements are already satisfied; do not call it merely to inspect availability.
5. Read back `gh pr view <number> --json state,autoMergeRequest,headRefOid,mergeCommit,mergedAt` and report whether auto-merge is queued or the PR already merged. Report deployment separately. Do not infer success from the command being attempted.

If new work invalidates evidence, disable queued auto-merge before pushing it, then verify the updated revision and re-enable. If the PR already merged, use a follow-up PR. GitHub cannot evaluate prose-only acceptance gaps, so do not queue while those remain. When multiple PRs overlap, integrate in dependency order and recheck the remaining branches.

If auto-merge or protection is unavailable, leave the PR open with a precise blocker. Do not silently substitute an unconditional merge or a custom privileged workflow. Skill instructions cannot guarantee that every agent obeys; required server-side checks enforce the mechanical gates.

GitHub documentation: [automatic merging](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/automatically-merging-a-pull-request) and [repository auto-merge settings](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-auto-merge-for-pull-requests-in-your-repository).
