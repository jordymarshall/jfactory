# Repository adoption

First read existing owner instructions, relevant product requirements, task/status records and the code. Find the project's existing homes for intent, architecture, status and agent instructions. Preserve them. Keep the root AGENTS.md entry point short and link details rather than copying them. Missing context triggers investigation and consequential questions; it does not authorize a rewrite or speculative feature work.

Establish the first bounded outcome and its acceptance criteria. Identify the riskiest unproven dependency, such as source data, auth or provider behavior. Distinguish owner choices, recommendations and unknowns. In an empty repo, build the agreed first runnable slice before writing verification instructions against actual controls.

Inventory executable capabilities:

- Start/build/test commands and dependency prerequisites.
- Actual customer entry points, routes/commands and account/data prerequisites.
- Existing unit, component, integration, application and provider checks. Note which are mocked.
- The safe test target and whether concurrent instances have separate ports, accounts and data.
- CI triggers, skipped checks, required checks and release triggers. A workflow file alone does not prove branch protection is enabled.
- Agent host capabilities: shell, browser, subagents, PR tools, evidence storage and instruction discovery.
- Installed jfactory version, concurrent workspaces, shared resources and PR dependencies, using [worktree coordination](worktrees.md). Establish one adoption PR as the source of workflow updates for this project.

For a browser product, establish a real browser session and evidence path using the [UX skill](../skills/jfactory-ux/SKILL.md). Distinguish public access, a dedicated signed-in account, and missing access. Prove the driver on a safe local task before claiming it works with a subscribed app. Reuse the host's browser tools when they provide the required observation and capture; the bundled Playwright CLI helper is a fallback. Keep private research artifacts and profiles out of commits and public preview services.

Reuse existing tests. Read the original `create-verification-skill` to create missing project instructions; use `maintain-verification-skill` for drift. Apply jfactory's verification contract as the local scope constraint. Generate a project-local verifier under the host's skill directory with launch, doctor, drive, evidence, cleanup and a feature map. Prove a mapped journey end to end before calling the verifier operational. Component-only success is partial readiness if the target behavior requires the full application.

Map the initial critical customer journey, including navigation, authorization, persistence/readback, failures/retries and downstream handoffs that apply. Do not stop at whichever fixture is easiest. If safe auth/data/provider access is missing, record the exact missing prerequisite and continue lower-scope checks without promoting their claims.

Integrate recurring deterministic checks into existing CI where authorized. Require a review of CI changes; do not edit remote branch protection or enable production automation as an incidental setup action. Document gaps that still rely on instructions.

When adopting the default auto-merge workflow, establish the owner's standing merge/release policy and the actual server-side gates using [auto-merge setup](auto-merge.md). Configure authorized settings where access permits; report inaccessible settings without claiming activation.

Setup handoff: canonical document links, first agreed task and acceptance criteria, actual commands executed and proof, remaining gaps and PR. No universal “works everywhere” claim: verify the chosen host and application in the target repository.
