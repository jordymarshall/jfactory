# Deliver reviewable work

The default result of an authorized code change is a PR, not a direct push to the base branch. Explicit user exceptions apply only to their stated scope.

1. Inspect git state, remote default branch, existing PR and applicable CI/deployment triggers. Preserve unrelated edits. If on the base branch, create a task branch or isolated checkout without renaming the user's current branch. Do not force-push shared history. Follow [worktree coordination](worktrees.md) when other branches or PRs touch this work.
2. Complete the agreed change, relevant checks, documentation and evidence. Review the diff for defects, accidental secrets, unrelated work and weakened assertions. Use upstream interrogate for a requested or warranted independent review and identify actual reviewer/model limits.
3. Commit only intended files and push the task branch. Opening a PR is part of delivery under this workflow, but inspect consequential automatic effects first. If PR creation would deploy against real data or incur new costs outside authorization, prepare the concrete local result and resolve only that missing authorization.
4. Open or update the PR against the correct base, ready for human review by default. Omit `--draft`. Use a structured body or `gh pr create --body-file <file>` to preserve literal text. Include customer-visible change, decision/inference, criterion-to-evidence summary, gaps, and reproduction/review instructions. Drafts are an explicit user or repository exception. Review status never means that missing required proof passed. Put failed, pending or blocked verification near the top of the PR when present.
5. Observe the checks for the pushed revision, address in-scope failures and report running or blocked checks honestly. Review feedback may start another engineering iteration. When authorized to convert an existing draft, preserve its gaps in the body and use `gh pr ready`; do not change unrelated PRs. Do not merge, enable auto-merge, push the base branch or trigger deployment without separate authorization.

Report the PR URL and remote head SHA. If no remote, credentials, or PR capability exists, preserve the local commit/patch and state that PR delivery is blocked. Never fabricate a URL or treat an installed skill as proof release gates are configured. A ready PR means ready for human review, not customer acceptance or permission to release.

## Evidence in the completion message

The user may only see the final message. Make it self-contained and concise, linking to details rather than hiding verification in earlier updates. Include:

- The agreed outcome, consequential owner decisions and any agent assumptions.
- What actually changed, and how the user can try it.
- What was checked: actual commands or user actions, observed results, tested revision/environment and evidence links. State whether evidence is from components, the application, real providers or a deployment. Name failed, skipped, pending and blocked checks.
- The PR link and remote head, plus unresolved acceptance or integration gaps. State owner acceptance only when it happened.

For a scene-audio change, inspect and test trimming, reordering and mute behavior, including playback/timing and persistence where required. A component test or encoded-file check proves its own scope; it cannot establish that the whole signed-in editor/render journey passed. "Confirmed, audio stays attached" without the actual checks and evidence is an incomplete handoff. If the turn only records an owner decision, say that explicitly and do not imply new implementation or verification.

The installation receipt identifies the distributed source version; it does not prove the agent followed the workflow. Command receipts can check freshness and coverage, but a reviewer must inspect whether assertions prove the agreed behavior. Required CI and branch protections can enforce chosen mechanical gates after repository-specific setup; prose instructions alone cannot guarantee compliance.
