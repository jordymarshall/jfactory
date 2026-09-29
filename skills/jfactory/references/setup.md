# Set up or reconcile a repository

Setup has five steps, and each leaves something `scripts/setup_check.py` can check:

1. **Inspect and resume:** install or update the bundle, then read the setup record at `.jfactory/setup.md`.
2. **Reconcile the foundation:** clean up the docs, put the four entry sections in `AGENTS.md`, and interview the owner. The answers go in the record.
3. **Prepare tools and verification:** set up bootstrap and doctor, the project verifier, `.jfactory/verification.json` through [guided mapping](mapping.md), a start-up receipt for each place the app runs, the change-aware CI job and the `jfactory verified` workflow.
4. **Establish the loop and delivery:** name the task location, write the next objective, record `merge_deploys` and the release procedure, and set up the GitHub gates.
5. **Deliver:** run `setup_check.py --remote` and open one adoption PR with the readiness report.

The same steps apply to every repository. Keep project facts in project-owned files, never in the jfactory bundle, and never tailor the bundle to one product.

"Setup jfactory" invokes this whole procedure. Installation only places the tools and entry instructions. Continue through repository adoption in the same session by reading the installed skill directly; reload discovery afterward if the host needs it. Do not stop at a successful copy or require the owner to name the remaining skills.

Setup authorizes the repository's workflow work, including reconciling stale documentation. It does not select a new product direction, build a speculative feature, or grant production access. Carry existing decisions and authorizations forward. Ask only for unresolved intent or access that affects the next action, and continue independent work while waiting.

## 1. Inspect and resume

Inspect applicable instructions, Git state, remote/base, installed version and host capabilities. Follow [worktree coordination](worktrees.md) to preserve ongoing work and identify an existing adoption PR. Reuse that work where possible. Do not overwrite another agent's branch or run parallel adoptions against the same files.

On an explicit setup/update request, compare the installed receipt with the project's chosen upstream revision. Respect an intentional pin. If unpinned, fetch and inspect the current upstream default branch, install the reviewed revision with the supported installer, then read the newly installed instructions and run `setup_check.py`. An update can add setup requirements; the checker reports each one the project does not meet yet, so fix them in the same adoption PR. Record the source revision and any local modifications; an unavailable upstream check is a visible gap. Normal feature work uses the installed version and does not silently upgrade it.

Read the existing setup record, if any. It lives at `.jfactory/setup.md`, created from [the template](../templates/setup-record.md) and linked from the agent instructions. If an older adoption kept its record elsewhere, move it there and leave a pointer. The checker reads its readiness table, owner interview and task location, so keep those headings. Record current readiness, evidence and remaining actions there. Re-running setup refreshes this record and repairs drift; it does not create a new checklist, roadmap or dated status file.

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

Explain the main customer journey and largest gaps in plain language. Then interview the owner. This step is required: code establishes what exists, not what the customer should want, and a brief the agent writes alone is an assumption. Ask each question in the setup record's interview table:

- who is struggling;
- what they do today, and what hurts;
- the outcome they would notice, and how improvement would be measured;
- what is out of scope;
- the next bounded objective.

Ask even when you can infer an answer, and offer your inference as the recommended option. Ask a few questions at a time. If the host has a structured question tool, ask one question per call, because some hosts drop answers from multi-question forms. Offer a recommended first outcome and alternatives with tradeoffs. Record each answer in the table with its date. Reuse answers from earlier setups and ask only what is still open.

Product direction stays `blocked` while every question is unanswered, and cannot be `verified` while any is. The checker enforces both. Do not delay unrelated tooling or documentation work for a product answer.

## 3. Prepare the development and verification tools

Read [environments and host setup](environments.md). Reuse or repair the project's existing bootstrap and doctor commands. Add a small repeatable command only where one is missing. Match the project's runtime and lockfile, install required dependencies, and handle fresh-workspace prerequisites. A doctor should report missing tools, configuration and access clearly without printing secrets or crashing on an absent executable. Separate dependency presence, reachable application and validated authentication.

Reuse existing tests. Read the original `create-verification-skill` for a missing project-local verifier or `maintain-verification-skill` for drift, subject to the [verification contract](verification.md). Keep project verification outside the managed jfactory bundle. Include launch, doctor, drive, evidence, cleanup and the feature map; link existing commands instead of rebuilding their test framework. Put repeatable launch/drive/capture steps in a small CLI inside the verifier's skill directory so every session runs the same commands, and record in the feature map how a user reaches each feature: navigation, shortcuts and stable selectors.

For browser products, set up the [UX skill](../skills/jfactory-ux/SKILL.md) and a private evidence location. Use a host browser when it supports the needed interaction/capture, otherwise the supplied Playwright helper. A missing login triggers its proactive human handoff. Do not request credentials in chat or assume another worktree's profile is available. Competitor exploration happens when requested or relevant to a specific design question; adoption alone does not require studying a subscribed app.

Create `.jfactory/verification.json` by following [the guided mapping procedure](mapping.md) step by step. Do not improvise it: it inventories the repository and names features from what users do. It maps shared code without pulling in every journey, and defines suites that can run alone with measured minutes. It records where the app runs and proves it starts in a fresh workspace with `verify_plan.py smoke`. It also sets risk levels and a per-PR budget with the owner, and audits until clean. Anything users see, stored data, sign-in and permissions, money, security, agent instructions and the enforcement scripts stays `independent`. Install the [`jfactory verified` workflow](../templates/jfactory-verified.yml) and the [change-aware CI job](../templates/jfactory-checks.yml) with the bundle path set. A tooling repository without a UI has no browser suite or target. `setup_check.py` fails on unmapped files, undefined suites, checks on every PR that exceed the budget, and targets without a passing start-up receipt when verification is marked verified.

Select an existing critical journey, not whichever fixture is easiest. Verify the applicable navigation, authorization, action, resulting state, persistence/readback and downstream side effects. Component checks cover responsive layout, interaction states and substituted boundaries. They cannot establish full-app or provider readiness. Include error/recovery, keyboard and motion checks where relevant to the journey. Capture the revision, target and observed evidence.

An empty repo has no existing journey to prove. Establish the first proposed runnable slice and prerequisites, with lint, types and CI from the first commit so later agents copy guarded patterns ([correction ladder](methodology.md#the-correction-ladder)), record application verification as not yet available, and wait for agreement before building product behavior. If the owner explicitly defers live testing, prepare the commands and criteria, record "not run by request", and never mark that scope verified. Missing access keeps the affected scope open while independent setup continues.

## 4. Establish the autonomous loop and delivery policy

Choose the task location where objectives live, for example the project's GitHub issues with a `jfactory-objective` label, or its existing tracker. Record it as `Task location:` in the setup record and in the agent instructions. Put the next bounded objective there using the [objective contract](verification.md#objective-contract) and [its template](../templates/objective.md), marked proposed until the owner agrees. Connect the customer outcome to concrete observations, executable checks and required evidence scopes. Identify the riskiest unknown, permitted data/services, any cost or iteration limits, next owner checkpoint and conditions for stopping. Setup has its own objective; suggesting a product task does not authorize implementing it.

The agent chooses an unresolved criterion, implements or investigates, runs the check, reads the result and side effects, corrects failures, and repeats within scope. It must not weaken criteria to make the loop finish. Failed attempts should inform the next attempt. If no new evidence supports another retry, diagnose the blocker or ask the consequential question while advancing independent work. A completed objective ends that loop. Record the next action so another session can resume without asking the owner to reconstruct the conversation.

Inspect actual CI coverage, including skips, and integrate appropriate deterministic checks into existing CI. Establish what is checked locally, in a PR preview, in a staging environment and after release. Follow [auto-merge setup](auto-merge.md) to carry forward or establish the standing merge/release policy. Configure authorized server-side gates when access permits, starting from the [ruleset template](../templates/ruleset-main.json) as described in [auto-merge setup](auto-merge.md#establish-the-repository-gates-once); if the agent's token cannot edit rulesets, prepare the filled-in file and give the owner the browser steps and the one-line `gh` command. Missing settings access, proof or authorization remains a named blocker; a workflow file is not proof of branch protection.

Record whether pushing or opening a PR creates a preview and whether merging deploys. Apply the [default release policy](auto-merge.md#default-policy-verified-work-merges-itself-production-does-not): merges deploy at most to staging, and production is released only on a deliberate owner request. Where merging releases production today, prepare the authorized change to a staging target and an owner-approved production release using the patterns in [production releases](release.md#choose-a-release-path), or report it as a delivery blocker. Record the result as `merge_deploys`. When merging deploys to staging, record how production is reached as the `release` block described in [production releases](release.md#record-the-procedure): the staging and production targets, how to read the commit each runs, the promote and rollback steps and the approval gate. The checker requires it before PR delivery can be `verified`. Setup records the procedure; it does not release. Identify deployment integrations outside CI too. Default to a non-draft PR. Enable protected auto-merge only when the repository policy, task proof and enforced gates permit it. Setup does not silently turn on a campaign, create follow-on workspaces/sessions, or start a new feature after merge. Record `merge_deploys` in `.jfactory/coordination.json`; the coordination tool refuses to merge without it. Where Conductor is used, also record the owner's concurrency limit and model policy there when they differ from the [defaults](coordination.md#model-policy), and confirm the tools coordination needs: `gh` can create, edit and comment on issues and create labels, `conductor auth whoami` succeeds, and the repository is added to the organization's Conductor cloud machine (otherwise `conductor workspace create` fails with HTTP 400 and the owner must add it in Conductor's organization settings). Report missing access as a coordination blocker with the exact owner step. Setup prepares coordination; it does not start a program. Explain [workspace and session lifecycles](worktrees.md#workspaces-sessions-and-deployments) in the project instructions when the host supports them.

## 5. Deliver an honest setup result

Review the adoption diff, document moves/deletions and repaired references. Run checks appropriate to the changed tools/docs and any approved live verification. Then run `python3 <skill>/scripts/setup_check.py --remote`. It exits 0 when setup is complete and 3 when it is consistent but blocked on named owner steps. Exit 1 means an artifact is missing or the record claims something the evidence does not support. Fix every exit-1 item before opening the PR, and paste the checker's summary into it. Open one adoption PR following [delivery](delivery.md). Link to the existing records instead of pasting an entire audit into the handoff.

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
