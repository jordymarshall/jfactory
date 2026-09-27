# Deliver reviewable work

The default result of an authorized code change is a PR, not a direct push to the base branch. Explicit user exceptions apply only to their stated scope.

1. Inspect git state, remote default branch, existing PR and applicable CI/deployment triggers. Preserve unrelated edits. If on the base branch, create a task branch or isolated checkout without renaming the user's current branch. Do not force-push shared history.
2. Complete the agreed change, relevant checks, documentation and evidence. Review the diff for defects, accidental secrets, unrelated work and weakened assertions. Use upstream interrogate for a requested or warranted independent review and identify actual reviewer/model limits.
3. Commit only intended files and push the task branch. Opening a PR is part of delivery under this workflow, but inspect consequential automatic effects first. If PR creation would deploy against real data or incur new costs outside authorization, prepare the concrete local result and resolve only that missing authorization.
4. Open or update the PR against the correct base. Use a structured body or `gh pr create --body-file <file>` to preserve literal text. Include customer-visible change, decision/inference, criterion-to-evidence summary, gaps, and reproduction/review instructions. Ready requires relevant technical criteria to pass; missing required proof means draft with explicit gaps, not a green claim.
5. Observe the checks for the pushed revision, address in-scope failures and report running or blocked checks honestly. Review feedback may start another engineering iteration. Do not mark a PR ready while required checks are failed or unresolved. Do not merge, enable auto-merge, push the base branch or trigger deployment without separate authorization.

Report the PR URL and remote head SHA. If no remote, credentials, or PR capability exists, preserve the local commit/patch and state that PR delivery is blocked. Never fabricate a URL or treat an installed skill as proof release gates are configured. A ready PR means ready for human review, not customer acceptance or permission to release.
