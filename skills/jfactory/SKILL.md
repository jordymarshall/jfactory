---
name: jfactory
description: Run connected product, UX and engineering loops with explicit objectives, browser research, executable verification, evidence and a pull request. Use for repository setup, features, fixes, app experience research and preparing changes for review.
---

# jfactory

Work proactively inside the user's objective. This is a portable engineering workflow built around selected, pinned Lauren Tan pstack skills. Read [host compatibility](references/compatibility.md) before using upstream methods. Repository decisions and current user authorization govern scope. Do not import another project's customer assumptions, architecture, credentials or release permissions.

For a plain explanation of the feedback paths and owner checkpoints, use [how the loops work together](references/methodology.md).

## Set up the repository once, reconcile when needed

Follow [repository setup](references/setup.md) when adopting jfactory or when missing context prevents sound work. Inspect the repo before asking factual questions. Preserve existing AGENTS.md and product documents. Identify the actual user interface, dev commands, architecture, acceptance records, tests, CI, safe data environment and default branch. On a blank project, architecture is proposed and capabilities are unimplemented until built.

Clarify unresolved intent and consequential experience choices before dependent implementation. Use an existing product/grilling skill if available; otherwise ask focused questions with recommendations. jfactory does not mandate a whole-product interview for every bug or replace the owner's product process.

## Establish and resume an objective

Record the useful outcome, owner decisions versus agent assumptions, scope/non-goals, observable acceptance criteria and next review point in the existing task. State the objective and how it will be checked before substantial implementation. On continuation, read that record and relevant code/evidence; do not require the user to repeat it. If the objective is complete, propose the next one rather than silently expanding scope.

At the start of repository work, identify the loaded jfactory path and installed source revision when available. For concurrent workspaces or overlapping PRs, follow [worktree coordination](references/worktrees.md). Instructions and evidence in another checkout are not automatically current here.

Use the [verification contract](references/verification.md) to map every criterion to required evidence scopes. The supplied evidence runner can record real commands and check freshness/coverage. It does not judge whether a test meaningfully proves the customer outcome. Inspect the assertions and actual result yourself.

## Implement, observe, correct

For meaningful interface changes, proactively use the [UX skill](skills/jfactory-ux/SKILL.md) to inspect the running experience and iterate against the agreed customer task. Use its reference-research mode when the user requests app research or a specific design uncertainty warrants it. Competitor observations inform proposals; they do not become requirements without product alignment. A CLI/API-only change does not need browser research.

Choose the next unresolved criterion. Investigate actual code, implement the smallest coherent change, run the relevant check, inspect the result and side effects, and correct failures. Continue without waiting for “keep going.” Preserve the acceptance standard. After repeated failure without new evidence, change the investigation or identify a concrete blocker; continue independent in-scope work.

Select only relevant original methods from [pstack routing](references/pstack.md). Use focused regression tests where practical, real application journeys for user-facing changes, and independent review proportionate to the change. Investigation/review instructions may request bounded subagents when the host permits them. Larger competing implementations or unattended campaigns require the user's request.

Update affected canonical documentation with material decisions and results. Keep requirement, implementation, verification and owner acceptance separate. Preserve historical proof and mark affected old evidence stale. Avoid a new plan or status file every turn.

## Deliver a pull request

Follow [PR delivery](references/delivery.md). Use a task branch or isolated checkout, commit only the requested work, push that branch and open a PR against the repository's actual base branch. The default is to enable protected auto-merge once task verification and any required owner decisions are complete, within the repository's authorized merge/release policy. An owner-approved standing auto-merge policy needs no repeated permission. Check the gates in [auto-merge setup](references/auto-merge.md); do not bypass checks, push the base branch directly, or infer permission for unrelated releases.

Open PRs ready for human review by default, without `--draft`; use drafts only when requested or required by an applicable repository rule. Review status is separate from verification and merge readiness. If required behavior failed, is unchecked or blocked, continue feasible work, then name the missing proof prominently in the PR and handoff. Never call incomplete verification complete. Documentation-only work needs appropriate documentation checks, not invented browser tests. Every completion message must include the concise evidence handoff in [PR delivery](references/delivery.md), including the PR URL and remote commit. A local commit or a bare "confirmed" is not a delivered, verified result.

## Improve the workflow from failures

Use the original eval playbook for substantial workflow changes or recurring agent failures. Check actual execution and artifacts, with realistic isolated tasks and a blinded judge; report available model/tool limits. Prefer tests, types, lint or CI enforcement for recurring mechanical failures. Do not claim a syntax check proves skill effectiveness, a model score proves correctness, or an installed skill guarantees compliance.
