# Coordinate several workspaces

Use this procedure when the owner asks one agent to deliver several objectives through separate Conductor workspaces, or when a program would outlive one session. One objective that fits a single session stays in one workspace under the normal jfactory loop. Parallel workspaces multiply cost and integration work; start them only on the owner's request or explicit agreement.

There are three roles:

- **Owner.** Decides outcomes and product questions, supervises through the program issue and the coordinator's chat, and can stop everything with one label.
- **Coordinator.** The agent the owner asked. It frames the program, writes task contracts, launches and monitors workers, verifies results, merges and reports. It does not edit a worker's files; code changes and conflict resolution are worker tasks.
- **Worker.** One agent per unit in its own workspace and branch. It follows the normal jfactory loop for its unit and reports to the program issue.

Read the pinned originals this adapts: [orchestrate](../vendor/pstack/skills/poteto-mode/playbooks/orchestrate.md), [multi-PR plan](../vendor/pstack/skills/poteto-mode/playbooks/multi-phase-plan.md), [prototype](../vendor/pstack/skills/poteto-mode/playbooks/prototype.md), [session pickup](../vendor/pstack/skills/poteto-mode/playbooks/session-pickup.md), [pause safely](../vendor/pstack/skills/poteto-mode/playbooks/pause-safely.md) and [sequence verifiable units](../vendor/pstack/skills/principle-sequence-verifiable-units/SKILL.md). Their Cursor-specific tools are translated in [host compatibility](compatibility.md#coordination-translations). Repository policy, owner decisions and this procedure take precedence.

## The coordination tool

`scripts/coord.py` in this skill enforces the mechanical rules. Run it from the repository root with `python3 <skill path>/scripts/coord.py <command>`; `--help` lists every command. It needs an authenticated `gh` and, for launching, the `conductor` CLI.

| Command | Who | What it does |
| --- | --- | --- |
| `init --title --outcome [--standing FILE] [--base] [--limit] [--merge-deploys]` | Coordinator | Creates the program issue labelled `jfactory-program` with the model policy and standing orders, plus a Conductor sidebar section containing the coordinator workspace |
| `list` | Anyone | Lists open program issues, for resuming |
| `add <issue> <unit> --objective --requires SCOPES [--role] [--effort] [--depends] [--paths]` | Coordinator | Adds a planned unit with the evidence scopes that define verified, its role (`implement`, `fast`, `trivial` or `verify`) and difficulty-based effort |
| `brief <file>` | Coordinator | Checks a task contract has every required field |
| `launch <issue> <unit> --brief FILE [--dry-run] [--stack-on UNIT] [--fallback --reason] [--agent/--model/--effort]` | Coordinator | Creates the unit's Conductor workspace with the policy's agent and model, moves it into the program's sidebar section, after checking hold, concurrency limit, dependencies, open decisions, brief completeness, attempt limit, model availability and reviewer model family |
| `report <issue> <unit> --state ...` | Worker | Posts a structured comment with its state, PR, head SHA, note or question |
| `sync <issue> [--dry-run]` | Coordinator | Folds worker reports, PR state and session status into the issue, voids verdicts on new heads and lists units ready to launch, including verifiers whose target has a PR (with the `--stack-on` to use) |
| `verdict <issue> <unit> --head --verdict --scopes --evidence --verifier [--full] [--features]` | Coordinator | Records verification only at the PR's current head, requires every declared scope, and posts the PR verdict that the `jfactory verified` status reads. The implementer is the unit's launched model, so units launched outside the tool cannot be verified through it |
| `merge <issue> <unit>` | Coordinator | Queues protected auto-merge pinned to the unit's current head. It needs a `verified` verdict at that head, unless the base branch's mapping marks every affected feature `verify: ci`; then GitHub's required CI is the gate. It also needs no open decisions, and a recorded `merge_deploys` of `staging` or `none` |
| `gate add` / `gate resolve` | Coordinator | Records an owner decision and its answer; open decisions block launch and merge for their units |
| `set <issue> <unit> --state` | Coordinator | Marks a unit blocked, failed or abandoned with a note |
| `close <issue>` | Coordinator | Closes the program only when every unit is merged, done (verifiers without their own PR) or abandoned |

The issue body has one writer, the coordinator. Workers never edit it; they add report comments, and the newest report after the coordinator's last change to that unit wins at the next `sync`. This avoids concurrent edits to one body. Anyone with comment access could post a report, so the coordinator still checks each claim against the actual PR.

The tool is a guard, not a supervisor. It runs only when an agent calls it, and it does not judge whether evidence is meaningful.

## Model policy

Each unit has a role, and each role is one tier of [model selection](models.md). The tool builds its roles from the same table as the usage reader, so the two cannot drift:

| Role | Tier | Use |
| --- | --- | --- |
| `implement` (default) | Frontier | Features, fixes, prototypes and other code changes that need strong judgment |
| `fast` | Fast | Well-scoped routine edits, follow-up fixes with a known cause, CI triage |
| `trivial` | Trivial | Renames, copy and formatting changes, lookups |
| `verify` | Verify | Verification, review and PR follow-through for another unit, always from a different model family than its implementer |

Use `launch --fallback --reason "<usage reading>"` only when the primary has no usage remaining; the reason is recorded on the unit. A verifier's family switch after Codex implementation happens automatically and is recorded as `alternate`, not as a fallback.

Every role chooses effort per unit by difficulty, from `low` to `high` (default `medium`). Use `low` for mechanical edits and narrow checks, `medium` for ordinary features and reviews, and `high` for ambiguous, cross-cutting or high-risk work. Set it with `add --effort` or `launch --effort`; the tool refuses levels outside the role's range. Raise effort on a retry when the previous attempt failed from difficulty rather than a bad contract. The exception is Opus 5.5 as a fast, trivial or verify model, which always runs at `low` effort: the tool applies it whatever the unit's effort, and refuses `launch --effort` with another level.

A repository overrides the policy in `.jfactory/coordination.json`, for example `{"limit": 2, "merge_deploys": "none", "roles": {"implement": {"effort": "high"}}}`. A role override changes only the fields it names; the fallback and other fields stay. Setup records the owner's policy there. `init` copies the effective policy into the program issue, so later edits to the file do not change a running program. `launch --agent/--model/--effort` overrides one unit and is recorded on it. The tool refuses models Conductor does not offer (`conductor model`), fast mode on a model without it, and a verifier from the same agent family as the unit it reviews. `--allow-same-family` only permits the launch. Whether a same-family verdict counts is the owner's decision recorded as `"allow_same_family": true` in `.jfactory/verification.json`; without it, `verdict` refuses to post one and the `jfactory verified` status rejects it. Disclose that decision in the PR.

## Where the owner is in the loop

| Moment | What the owner does |
| --- | --- |
| Framing | Agrees the outcomes, acceptance criteria, units, limit and policy. Answers product questions before workers start. |
| While running | Opens the program issue to see units, PRs, verdicts and open decisions. Answers decisions in the coordinator's chat or as issue comments. |
| Direct feedback | Opens any worker from the program's sidebar section and messages it, tries its preview, or comments on its PR. The worker applies feedback within its unit and reports it as an owner decision; the coordinator records it and relays it to affected units. Feedback that changes scope comes back as a decision instead of silent expansion. |
| Stop | Adds the `jfactory-hold` label. `launch` refuses, and each worker is told at its next report to stop at a safe boundary and push. Removing the label resumes. |
| Results | Receives each PR with its walkthrough and evidence, and the coordinator's checkpoint reports. Tries the result and gives product feedback. |

GitHub usually does not notify you about actions taken with your own token, and agents typically use it. Do not rely on issue notifications; the coordinator's chat reports are the active channel, and the issue is the dashboard.

### Why separate workspaces instead of sessions

Sessions in one workspace share its checkout, branch, running processes and ports. Two implementing sessions would overwrite each other's files, produce one mixed branch and PR, and contend for the same dev server. A workspace per unit gives each worker its own checkout, branch, PR and cloud machine, so it can run and verify the app independently. Use an extra session only for an agent that should read the same checkout, such as a reviewer or explainer that does not write.

## 1. Frame the program with the owner

State, once, before any worker starts:

- The program objective and a countable done condition, for example "these three outcomes are merged, each with its required application evidence at the merged revision."
- The units. One unit is one coherent objective delivered as one PR with its own evidence. Name dependencies and each unit's owned paths.
- Each unit's verification standard: its acceptance criteria and the evidence scopes that define verified (`add --requires`, such as `application,unit`). Application evidence comes from the PR preview or staging. Workers loop until the standard passes; the coordinator merges without asking again once it does.
- The concurrency limit (default three), the model policy (see [model selection](models.md), including the usage check before each launch batch), wall-clock or spend limits, and what merging deploys (`init --merge-deploys` or `.jfactory/coordination.json`). `merge` refuses unless merges reach staging or nothing; production releases stay a deliberate owner action.

Run the product interview for each substantial feature before its worker starts, reusing settled answers. A worker cannot interview the owner mid-flight without stalling, so unresolved product choices are settled here or recorded with `gate add`. Reversible preparation can proceed while the owner reviews the framing.

If one session could finish the work inside the budget, say so and do it in one workspace.

Then run `init` with the standing orders: numbered constraints that apply to every worker, such as delivery policy, forbidden paths, shared-resource rules and escalation rules. `add` each unit. When you catch yourself restating an instruction to a worker, add it to the standing orders instead.

## 2. Resolve uncertainty before writing tasks

- An open visual, interaction or empirical question gets a throwaway [prototype](../vendor/pstack/skills/poteto-mode/playbooks/prototype.md) first, as an `implement` unit at low effort or in the coordinator's workspace. Keep its scratch path, revision and screenshots or observed output. The prototype informs the decision and does not ship.
- A contested module shape or a hard-to-reverse boundary gets [architect](../vendor/pstack/skills/architect/SKILL.md) before implementation units are cut.
- A shared API, schema or data contract lands as its own first unit. Dependent units wait for it to merge, or stack on its branch with `launch --stack-on` and a recorded merge order.

Product or preference choices that no prototype settles go to the owner with options and a recommendation.

## 3. Write a complete task contract per unit

The initial message is the worker's whole context. It cannot see sibling workspaces or this chat. Write every field; `brief` and `launch` refuse a contract with a missing field.

```text
OBJECTIVE      One sentence a stranger can execute, with the customer outcome.
DECISIONS      Owner decisions, recorded assumptions, and questions that are out of scope for this unit.
SCOPE          Paths this unit may change; paths it must not change; its branch name.
CONTEXT        Links to the program issue, task record, relevant files and PRs. Paste upstream unit results it depends on.
ACCEPTANCE     Observable criteria, one per line, with required evidence scopes; a judgment criterion carries its rubric.
VERIFY         Exact commands, application journey and environment; known limits of each.
SHARED         Accounts, databases, ports, previews and services, and whether this unit may mutate them.
LIMITS         Time or spend cap; on reaching it, push work, report partial results and stop.
FORBIDDEN      No force-push, no edits to other units' branches, no base-branch push, no work outside SCOPE.
DELIVERY       Ready-for-review PR to the base branch, linked to the program issue; auto-merge is queued by the coordinator.
REPORT         Status, branch, head SHA, PR, each criterion's result and evidence, deviations, blockers, follow-ups.
```

`launch` appends the standing orders and a coordination block that tells the worker its unit, the program issue and the exact `report` commands. Size the rest to the unit; a one-line fix can use one short line per field.

## 4. Launch workers

Before the first launch, confirm the base branch contains the jfactory adoption commit, so workers load these instructions and the tool, and that the repository's cloud setup script prepares dependencies.

Pilot one unit from contract to verified PR before launching the rest when the unit shape is new. Correct the contract and verification recipe from what the pilot reveals. For near-identical cheap units, the first unit is the pilot.

Before each launch batch, run the usage reader under [model selection](models.md) and pass `--fallback --reason` with its reading when it chooses a fallback. Use `launch --dry-run` to review the exact message, then `launch`. It records the workspace link and session on the unit and posts a launch comment. Use `conductor session create` only for an agent that should share an existing workspace, such as a same-checkout reviewer; two writers in one checkout are not isolated. Refill free slots as units finish instead of waiting for a whole batch.

## 5. Worker protocol

A worker whose task contract names a program issue:

1. Reports `running` when it starts.
2. Follows the normal jfactory loop for its unit only: objective contract, implementation, verification and a ready-for-review PR linked to the program issue. It does not queue auto-merge; the coordinator does after independent verification.
3. Reports `in-review` with the PR, head SHA and criterion results after each push that changes the PR, `blocked` with `--question` when it needs a decision, or `failed` with the reason.
4. Applies owner feedback given directly in its workspace within its unit, and includes it as an owner decision in the next report. Feedback that changes scope or affects other units is reported as `blocked` with a question rather than acted on alone.
5. Continues independent in-scope work while a question is open, and does not edit the issue body, launch workspaces or touch other units' branches.
6. Stops at a safe boundary, pushes and reports when a report prints `PROGRAM ON HOLD`, or when its limits are reached.

## 6. Monitor by evidence, not by interrupting

Run `sync` at natural points: after a critical step, on a scheduled wakeup, and before reporting to the owner. It prints counts, what changed, units whose session went idle without a final report, and units ready to launch. Use the host's scheduled wakeups with a long fallback interval rather than tight polling.

For detail, read `conductor session message <session> --after <last seen message id>` and the PR. Do not send a message to check progress; a message starts another turn and can redirect the worker. Send one with `conductor message create --session <session>` only to answer a question, deliver a changed dependency or correct scope, and restate the relevant standing orders when you do.

A worker question becomes an open decision at `sync`. Answer it from recorded decisions when possible with `gate resolve` and a message to the worker. Otherwise batch it for the owner.

## 7. Verify each result independently

A worker's report is a claim. At the PR's current head SHA, inspect the criteria, the checks that ran, the application evidence and whether the assertions prove the claim. Record the result with `verdict`. CI status is an input, not a verdict. For a unit whose changes are all `verify: ci`, still check the claim against the PR, but no verdict is needed: `merge` relies on GitHub's required CI. A new head voids the previous verdict at the next `sync`.

Every unit whose PR touches an `independent` (high-risk), unmapped or gate path gets a `verify` unit that depends on it (a unit whose changes are all `verify: ci` needs none). The verify unit is launched with `--stack-on` so it checks out the PR branch once the worker reports `in-review`. Its contract asks it to run `verify_plan.py smoke` for the target first and report a failed step as `blocked`, then re-run the acceptance checks at their required scopes, including the application journey only where a criterion needs it, review the diff and any mapping change, and follow the PR through CI and review comments. It runs `verify_plan.py plan` for the PR, reports a recommended verdict with evidence and does not change product code; defects become a fix task for the original worker. Choose its effort by risk. The coordinator inspects that evidence and records the `verdict`.
It runs on GPT Luna 6 in fast mode, or Opus 5.5 at low effort when the implementer ran on Codex; see the verify tier in [model selection](models.md). Archive the verifier's workspace once its verdict is recorded.

## 8. Integrate continuously

Land verified units as they finish rather than at the end. Follow [PR delivery](delivery.md), [worktree coordination](worktrees.md#deliver-and-integrate) and [auto-merge setup](auto-merge.md). `merge` queues protected auto-merge pinned to the unit's current head: after a `verified` verdict at that head, or, for a unit whose changes are all `verify: ci`, on GitHub's required CI alone. For overlapping units, merge one at a time. After each merge, message dependent workers to update from the base, rerun affected checks and report the new head. A conflict-free merge is not proof of combined behavior.

Finished workspaces are archived as soon as their unit finishes, not at program close, so the sidebar shows only live work. `sync` archives the workspace of every `merged`, `done` or `abandoned` unit once its session is idle, records it on the unit and reports sessions still working. Set `abandoned` only after the unit's work is pushed or deliberately discarded. `--keep-workspaces` skips archiving. Archive a workspace launched outside the tool, such as a probe or ad hoc reviewer, yourself with `conductor workspace archive <workspace id>`. Conductor's CLI archives workspaces; it does not delete them. Archived workspaces stay listed under `conductor workspace list --include-archived`. Archive only workspaces this program created. Leave the owner's own workspaces and other coordinators' workspaces alone, even when they look idle.

The coordinator does not force-push, retarget or close another worker's PR. Those actions are worker tasks or owner decisions.

## 9. Recover from failures and interruptions

- **Stalled or failed worker.** Read its last messages, branch and PR. A worker stopped by a usage limit has not failed: continue it on the role's fallback per [model selection](models.md#3-decide-record-and-revisit), which does not count toward the attempt limit. Otherwise, mark it `failed` with the reason and relaunch once with a narrower contract or another model when the failure warrants it. `launch` refuses a fourth attempt; abandon the unit with `set --state abandoned --note` and replan around it.
- **Late or duplicated output.** Reconcile it against the current base, program issue and ledger before accepting anything.
- **Program-wide failure.** When further launches would repeat the same failure, add the hold label, let running workers stop safely, fix the cause and remove the label.
- **Coordinator interruption.** A new coordinator session follows [session pickup](../vendor/pstack/skills/poteto-mode/playbooks/session-pickup.md): `list`, read the program issue, then `sync`. Resume from that state without relaunching finished units.
- **Owner-requested pause.** Add the hold label and follow [pause safely](../vendor/pstack/skills/poteto-mode/playbooks/pause-safely.md) for the coordinator's own work.

## 10. Escalate and close

Ask the owner only for product or preference decisions that no experiment settles, irreversible or unauthorized actions, standing orders that contradict observed reality, and dead ends that survived a replan. Batch these questions and keep routine retries, CI triage and merge mechanics out of them.

Confirm the done condition on the merged base, including required application evidence, then run `close`. It archives any remaining finished workspaces, deletes the program's sidebar section once none of its sessions is still working, and runs `tidy`. `tidy` deletes any other `Program:` section whose workspaces are all archived, or whose program issue is closed and none of whose remaining workspaces is still working. `close` never lets `tidy` delete its own section while one of its finished workspaces is unarchived. It never touches sections without the `Program:` prefix, and can run on its own. Before reporting, check `conductor workspace list --mine --repo <repository> --json` for anything the program launched outside the tool. Ask before archiving the coordinator's own workspace, which the owner may still be reading. Leave the owner's other workspaces and other coordinators' workspaces alone. Report the done condition, units and PR links, verdicts at merged SHAs, what was abandoned and why, remaining decisions and the program issue. Add recurring corrections to the standing orders template or an enforced check.

## What this does not provide

jfactory does not install a background supervisor, scheduler or webhook. Nothing launches or syncs unless an agent runs the tool, so a coordinator session that stops leaves workers running unsupervised until someone resumes it. Conductor routines can trigger agents from webhooks when the owner configures one separately. The tool's rules are tested against simulated `gh` and `conductor`; an end-to-end program with real workers has not yet been evaluated.
