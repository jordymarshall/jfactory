# Set up or reconcile a repository

"Setup jfactory" invokes this whole procedure. Installation only places the tools and entry instructions. Continue through repository adoption in the same session by reading the installed skill directly; reload discovery afterward if the host needs it. Do not stop at a successful copy or require the owner to name the remaining skills.

Setup authorizes the repository's workflow work, including reconciling stale documentation. It does not select a new product direction, build a speculative feature, or grant production access. Carry existing decisions and authorizations forward. Ask only for unresolved intent or access that affects the next action, and continue independent work while waiting.

## 1. Inspect and resume

Inspect applicable instructions, Git state, remote/base, installed version and host capabilities. Follow [worktree coordination](worktrees.md) to preserve ongoing work and identify an existing adoption PR. Reuse that work where possible. Do not overwrite another agent's branch or run parallel adoptions against the same files.

On an explicit setup/update request, compare the installed receipt with the project's chosen upstream revision. Respect an intentional pin. If unpinned, fetch and inspect the current upstream default branch, install the reviewed revision with the supported installer, then read the newly installed instructions. Record the source revision and any local modifications; an unavailable upstream check is a visible gap. Normal feature work uses the installed version and does not silently upgrade it.

Read the existing setup/task record, if any. Use one durable setup section in the existing engineering runbook or adoption task. If there is no suitable home, create one short setup record and link it from agent instructions. Record current readiness, evidence and remaining actions there. Re-running setup refreshes this record and repairs drift; it does not create a new checklist, roadmap or dated status file.

Inventory the docs and their callers, implementation entry points, commands, tests, CI/release triggers, safe data environments and host tools. For a large repo, inventory broadly, then read documents that govern current product, architecture, verification and delivery. Mark anything not audited. Do not claim every historical document is current after a sampled review.

If installed files or their managed instruction block were customized, reconcile the installer refusal before updating. Preserve useful project-specific behavior in project-owned instructions or verifier skills, then update the reviewed bundle. Do not bypass conflict detection or edit receipts to make a modified installation look clean.

## 2. Reconcile the foundation

Apply [documentation reconciliation](documentation.md), including nested agent instructions and project-owned skill adapters. Make the cleanup in the adoption diff, rather than merely recommending it. Keep four short entry sections in AGENTS.md, or the host's equivalent:

| Section | Canonical detail |
| --- | --- |
| Product brief | Customer, problem, customer hypothesis, experience goal, non-goals and unsettled decisions |
| System map | Current components, data flow, external services and environment boundaries |
| Feature/status map | Important journeys, implementation state, verified scope/revision and remaining gaps |
| Agent instructions | How to start/check the app, active task location, workflow, coordination and merge/release policy |

Use the existing homes for these facts; these are sections, not four mandatory new files. Keep the installation-managed block intact. Avoid maintaining separate competing instructions for different agent hosts; link their entry points to shared project policy where supported.

Explain the main customer journey and largest gaps in plain language. Code establishes what exists, not what the customer should want. Interview the owner deeply where the customer hypothesis or experience goal is unresolved. Cover who is struggling, their present workaround, the desired outcome, the end-to-end experience, what would demonstrate improvement, and what is excluded. Offer a recommended first outcome and alternatives with tradeoffs. Reuse settled answers; mark recommendations as proposals until accepted. Do not delay unrelated tooling or documentation work for a product answer.

## 3. Prepare the development and verification tools

Read [environments and host setup](environments.md). Reuse or repair the project's existing bootstrap and doctor commands. Add a small repeatable command only where one is missing. Match the project's runtime and lockfile, install required dependencies, and handle fresh-workspace prerequisites. A doctor should report missing tools, configuration and access clearly without printing secrets or crashing on an absent executable. Separate dependency presence, reachable application and validated authentication.

Reuse existing tests. Read the original `create-verification-skill` for a missing project-local verifier or `maintain-verification-skill` for drift, subject to the [verification contract](verification.md). Keep project verification outside the managed jfactory bundle. Include launch, doctor, drive, evidence, cleanup and the feature map; link existing commands instead of rebuilding their test framework.

For browser products, set up the [UX skill](../skills/jfactory-ux/SKILL.md) and a private evidence location. Use a host browser when it supports the needed interaction/capture, otherwise the supplied Playwright helper. A missing login triggers its proactive human handoff. Do not request credentials in chat or assume another worktree's profile is available. Competitor exploration happens when requested or relevant to a specific design question; adoption alone does not require studying a subscribed app.

Select an existing critical journey, not whichever fixture is easiest. Verify the applicable navigation, authorization, action, resulting state, persistence/readback and downstream side effects. Component checks cover responsive layout, interaction states and substituted boundaries. They cannot establish full-app or provider readiness. Include error/recovery, keyboard and motion checks where relevant to the journey. Capture the revision, target and observed evidence.

An empty repo has no existing journey to prove. Establish the first proposed runnable slice and prerequisites, record application verification as not yet available, and wait for agreement before building product behavior. If the owner explicitly defers live testing, prepare the commands and criteria, record "not run by request", and never mark that scope verified. Missing access keeps the affected scope open while independent setup continues.

## 4. Establish the autonomous loop and delivery policy

Put the next bounded objective in the existing task location using the [objective contract](verification.md#objective-contract). Connect the customer outcome to concrete observations, executable checks and required evidence scopes. Identify the riskiest unknown, permitted data/services, any cost or iteration limits, next owner checkpoint and conditions for stopping. Setup has its own objective; suggesting a product task does not authorize implementing it.

The agent chooses an unresolved criterion, implements or investigates, runs the check, reads the result and side effects, corrects failures, and repeats within scope. It must not weaken criteria to make the loop finish. Failed attempts should inform the next attempt. If no new evidence supports another retry, diagnose the blocker or ask the consequential question while advancing independent work. A completed objective ends that loop. Record the next action so another session can resume without asking the owner to reconstruct the conversation.

Inspect actual CI coverage, including skips, and integrate appropriate deterministic checks into existing CI. Establish what is checked locally, in a PR preview, in a staging environment and after release. Follow [auto-merge setup](auto-merge.md) to carry forward or establish the standing merge/release policy. Configure authorized server-side gates when access permits. Missing settings access, proof or authorization remains a named blocker; a workflow file is not proof of branch protection.

Record whether pushing or opening a PR creates a preview and whether merging deploys. Apply the [default release policy](auto-merge.md#default-policy-verified-work-merges-itself-production-does-not): merges deploy at most to staging, and production is released only on a deliberate owner request. Where merging releases production today, prepare the authorized change to a staging target and a manual production release, or report it as a delivery blocker. Record the result as `merge_deploys`. Identify deployment integrations outside CI too. Default to a non-draft PR. Enable protected auto-merge only when the repository policy, task proof and enforced gates permit it. Setup does not silently turn on a campaign, create follow-on workspaces/sessions, or start a new feature after merge. Where Conductor is used, record the owner's concurrency limit and model policy in `.jfactory/coordination.json` when they differ from the [defaults](coordination.md#model-policy), and confirm the tools coordination needs: `gh` can create, edit and comment on issues and create labels, `conductor auth whoami` succeeds, and the repository is added to the organization's Conductor cloud machine (otherwise `conductor workspace create` fails with HTTP 400 and the owner must add it in Conductor's organization settings). Report missing access as a coordination blocker with the exact owner step. Setup prepares coordination; it does not start a program. Explain [workspace and session lifecycles](worktrees.md#workspaces-sessions-and-deployments) in the project instructions when the host supports them.

## 5. Deliver an honest setup result

Review the adoption diff, document moves/deletions and repaired references. Run checks appropriate to the changed tools/docs and any approved live verification. Open one adoption PR following [delivery](delivery.md). Link to the existing records instead of pasting an entire audit into the handoff.

Report each applicable area separately in the setup record:

| Area | Evidence needed to call it ready |
| --- | --- |
| Documentation | Canonical links resolve; current instruction conflicts are reconciled; retained historical material is clearly marked |
| Product direction | Agreed customer/experience goal and bounded task, with assumptions and open decisions visible |
| Workspace tools | Bootstrap/doctor actually ran in the named host; persistent host setup registration verified separately |
| Verification | Each demonstrated scope has commands/actions, observed results and revision; missing scopes stay open |
| Environments | Test target, dependencies, account/data isolation and deployment identity established for the intended checks |
| PR delivery | Actual PR access and triggers established; merge/release policy and server-enforced checks confirmed |

Use `verified`, `configured but unverified`, `blocked`, `not run by request`, or `not applicable` with evidence or a reason for each area. Never collapse these into an unsupported "everything is ready". For each gap give the affected capability, next action and who can take it. Prepare everything feasible before handing off a settings or access step, then resume from this record when resolved.

End with what the owner decided, what the agent inferred, what now exists, what was actually verified, the PR and the next simple prompt. Do not call setup fully operational while required areas remain blocked. Commit portable instructions and sanitized evidence summaries; keep secrets, private profiles and raw sensitive artifacts out of Git.
