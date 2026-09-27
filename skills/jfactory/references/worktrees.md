# Work across worktrees and PRs

Each worktree or cloud workspace has its own checkout. It may have different instructions, code and evidence. Local worktrees can still share Git history and external services; cloud workspaces can still share accounts, data and deployments. Separate folders do not prevent integration conflicts.

## Start a task

1. Read this checkout's applicable instructions and jfactory skill. Inspect the installed `.jfactory-install.json` for `source_commit` and `source_dirty` when present, and name the loaded version at kickoff. A receipt records installation provenance, not current compliance; investigate local modifications or conflicting instructions. Never claim that another workspace's update is installed here.
2. Inspect branch, dirty files and remotes, fetch the intended remote, and identify the actual base. Preserve ongoing work. Use one branch and PR per coherent objective, with one writer per checkout. Do not switch another active agent's branch or write into its files.
3. List open PRs in the repository and inspect likely overlaps using their changed files and descriptions. For GitHub, use `gh pr list` and `gh pr view <number> --json files,headRefName,baseRefName,body`. Record dependencies and shared-file ownership in the existing task or PR, rather than starting a new global status document. Local worktree listings cannot discover separate cloud workspaces or unpublished changes. Disclose that visibility limit and clarify suspected unpublished overlap.
4. Independent changes branch from the current base and target it. When a task needs another unmerged change, wait for that PR or explicitly stack the dependent branch/PR onto it and record merge order. Avoid copying the same feature into sibling branches. Coordinate shared API/schema changes before dependent work.
5. Isolate dev-server ports, browser profiles, test accounts/data and temporary artifacts. Do not restart another workspace's shared service or overwrite its preview. If a shared resource cannot be isolated, agree on one owner or run those operations sequentially.

## Keep the installed workflow current

Update jfactory in one adoption PR in the application repository. Review and merge it through that repository's normal process. New workspaces inherit it only when their starting branch includes that commit. Existing workspaces do not auto-update, and a merged jfactory upstream PR does not update consumer repositories.

For an existing workspace, preserve or commit its work, fetch, and integrate the reviewed adoption commit through the normal branch update. Alternatively, install the reviewed upstream version with `--update` in that checkout and deliver its adoption diff. Avoid independently editing the managed bundle in every feature branch. Reload instructions or start a fresh session and confirm the loaded version. Do not silently replace local customizations; the installer refuses them for reconciliation.

## Deliver and integrate

Before delivery, fetch again, inspect base changes and overlapping PRs, and update the task branch if needed. Prefer merging the base into an already shared branch when that avoids rewriting history; rebase only when repository policy and branch ownership permit it. Never force-push someone else's history. Resolve conflicts by preserving the intended behavior of both changes, then rerun affected checks and the shared user journeys. A conflict-free Git merge does not prove behavioral compatibility. Evidence from before changed code or conflict resolution may be stale.

Link related PRs and merge order in the PR body. Opening for review is the default even when a dependency or verification gap remains; state those gaps prominently and do not claim merge readiness. After an upstream PR merges, refresh dependent branches, retarget stacked PRs to the actual base as appropriate, and verify their remaining diff and checks. Squash merges can require extra care to remove already-landed changes from a dependent diff.

Under the repository's standing auto-merge authorization, integrate one overlapping PR at a time, refresh the next, and verify the combined behavior. Follow [auto-merge setup](auto-merge.md) to establish actual server-side gates. A configured merge queue with required checks can enforce integration checks; installing the skill alone does not configure one. Report remaining conflicts or unverified combined behavior. Never promise zero conflicts.
