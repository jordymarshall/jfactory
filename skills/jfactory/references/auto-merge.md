# Set up and use protected auto-merge

The default delivery preference is a non-draft PR followed by auto-merge once the change is verified as right. Honor the target repository's owner-approved policy. A standing authorization covers subsequent in-scope PRs; do not ask again each time. Merely installing this skill in another owner's repository does not grant merge or production permissions.

## Default policy: verified work merges itself, production does not

This is jfactory's default unless the owner records otherwise:

- **Verified means right, proven.** Before implementation, each objective records its acceptance criteria, the job goals they add, change or rely on, and the evidence scopes each requires (see the [verification contract](verification.md)). The agent works until the change is right at the PR's current head: every criterion passes at its scopes, the standing goals of the jobs it touches still hold, it meets the standards map, and it serves the outcomes without crossing a non-goal. A passing test suite alone is not verified. For application criteria, use the PR preview or staging, not production. Then it queues auto-merge without asking again. Missing, failed or stale proof keeps the PR open. Never weaken the standard to reach a merge.
- **Merging deploys at most to staging.** The base branch should deploy to a staging target, or nowhere. If merging currently releases production, auto-merge stays off until the release path is reconfigured, with the owner's authorization, so merges reach staging or nothing. There is no auto-merge exception for merge-to-production.
- **Production is a deliberate owner action.** Release to production only when the owner asks for that release. A merge, green CI, a verified verdict or a standing auto-merge authorization is not a production request. Setup records the repository's release procedure, and the agent follows it on request, as described in [production releases](release.md). The one exception is an owner's recorded standing authorization (`"release_after_merge"` in `.jfactory/coordination.json`), typically before a product has customers: then each verified merge is released through the same procedure ([release after every merge](release.md#release-after-every-merge)).

## Establish the repository gates once

Inspect the repository's actual settings, branch protection/rulesets, required reviews, merge strategy and release triggers. The owner must know whether merging also deploys. Record that policy, and what merging deploys (`staging`, `none` or `production`), with the existing repository instructions and in `.jfactory/coordination.json` as `merge_deploys`. An existing auto-deploy pipeline is not separate evidence of release authorization. When authorization covers auto-merge but excludes its deployment side effect, resolve that conflict before enabling it.

On GitHub, enable **Allow auto-merge** under Settings → General → Pull Requests. Protect the default branch with the [ruleset template](../templates/ruleset-main.json). It requires PRs, squash merges, no bypass, branches up to date, your CI check and `jfactory verified`.

1. Replace `REPLACE_WITH_YOUR_CI_CHECK_NAME` with the name of the job your CI reports. Merge that job and the ruleset into an existing ruleset instead if the repository already has one.
2. Apply it with `gh api -X POST repos/<owner>/<repo>/rulesets --input <file>`. To update an existing ruleset, use `-X PUT .../rulesets/<id>`.
3. Commit the filled-in copy as `.github/rulesets/main.json`, so the intended settings are reviewable.
4. Confirm with `setup_check.py --remote`.

Rulesets need the repository Administration permission. Some agent tokens lack it; Conductor's GitHub App gets HTTP 403, for example. Then give the owner both options:

- **In the browser:** Settings → Rules → Rulesets → New branch ruleset, or edit the existing one. Add the same rules, then under "Require status checks to pass" add the CI check and `jfactory verified`.
- **From the owner's own signed-in `gh`:** run the same `gh api` command.

Rerun the checker once the owner confirms. On the target branch, require a PR, the change-aware CI aggregate check and the `jfactory verified` status from the [verification contract](verification.md#change-aware-verification-and-the-merge-gate). Do not require a fixed expensive suite for every change; the plan decides which suites a PR needs, and unknown files still require all of them. Prefer checks against the latest base or a supported merge queue for concurrent PRs. Preserve existing required reviews and protections; do not remove them to make automation faster. Configure these settings when the owner authorizes auto-merge setup and credentials permit it. If settings are inaccessible, describe the exact missing permission or plan feature. Do not change repository visibility or purchase a plan as a workaround.

Prefer squash merging when the repository has no established alternative. Keep shared task branches current by merging the base into them; use rebasing only when branch ownership and policy permit rewriting history. After any update, refresh affected proof before re-enabling auto-merge. Native auto-merge waits for gates; it does not itself maintain stale branches or start another agent session. The [stuck-PR check](coordination.md#the-stuck-pr-check) fills part of that gap: it merges the base branch into a verified PR that is behind, once per head, and reports every PR that stopped moving.

Consumer applications must select their own meaningful checks. A tooling repository might require a single integrity/test job; an application may also require browser, storage or provider checks. A workflow existing or passing once does not prove it is a required merge gate. A human screenshot of settings or an authoritative API response can establish settings when the agent cannot read them directly, but an unsupported assumption cannot.

A required check must fail when its mandatory work is missing. GitHub can accept a skipped job as a successful required status, so use an unconditional aggregate check that rejects failed, cancelled or skipped dependencies where those dependencies are required. Give narrower manual diagnostic runs a different check name so they cannot satisfy a full-suite gate. Shared test accounts/data require isolation or common concurrency control across branches, not only a per-branch lock.

## Enable it per PR

1. Review the actual diff and evidence at the current head. Complete required application/provider proof and owner decisions outside CI. Do not queue a PR with missing behavioral proof merely because its unit tests passed.
2. Confirm the intended base, permitted merge method, no unresolved failures or changes requested, and no unresolved dependency or conflict. Pending required CI is allowed only when the server enforces those exact checks. Refresh overlapping branches and verify combined behavior as described in [worktree coordination](worktrees.md).
3. Confirm merging reaches staging or nothing, per the default policy above.
4. With a protected target and squash permitted, use `python3 <bundle>/scripts/coord.py land --pr <number> --head <verified-head-sha>` (inside a program, `coord.py merge`). It runs `gh pr merge <number> --auto --squash --match-head-commit <verified-head-sha>`, waits for GitHub to merge, then archives the PR's finished workspaces; a bare `gh pr merge` leaves them for the next jfactory command. Use the repository's configured merge method or merge queue when different. Never use `--admin`. The command can merge immediately if requirements are already satisfied; do not call it merely to inspect availability.
5. Read back `gh pr view <number> --json state,autoMergeRequest,headRefOid,mergeCommit,mergedAt` and report whether auto-merge is queued or the PR already merged. Report deployment separately. Do not infer success from the command being attempted.

If new work invalidates evidence, disable queued auto-merge before pushing it, then verify the updated revision and re-enable. If the PR already merged, use a follow-up PR. GitHub cannot evaluate prose-only acceptance gaps, so do not queue while those remain. When multiple PRs overlap, integrate in dependency order and recheck the remaining branches.

If auto-merge or protection is unavailable, leave the PR open with a precise blocker. Do not silently substitute an unconditional merge or a custom privileged workflow. Skill instructions cannot guarantee that every agent obeys; required server-side checks enforce the mechanical gates.

GitHub documentation: [automatic merging](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/automatically-merging-a-pull-request) and [repository auto-merge settings](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-auto-merge-for-pull-requests-in-your-repository).
