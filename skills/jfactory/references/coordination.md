# Coordinate several workspaces

Use this procedure when the owner asks one agent to deliver several objectives through separate Conductor workspaces, or when a program would outlive one session. One objective that fits a single session stays in one workspace under the normal jfactory loop. Parallel workspaces multiply cost and integration work; start them only on the owner's request or explicit agreement.

The coordinator owns the program: outcomes, task contracts, dependencies, evidence review, integration order and owner questions. Workers own code in their own workspace and branch. The coordinator does not edit a worker's files. Code changes, conflict resolution and fixes are tasks for a worker.

Read the pinned originals this adapts: [orchestrate](../vendor/pstack/skills/poteto-mode/playbooks/orchestrate.md), [multi-PR plan](../vendor/pstack/skills/poteto-mode/playbooks/multi-phase-plan.md), [prototype](../vendor/pstack/skills/poteto-mode/playbooks/prototype.md), [session pickup](../vendor/pstack/skills/poteto-mode/playbooks/session-pickup.md), [pause safely](../vendor/pstack/skills/poteto-mode/playbooks/pause-safely.md) and [sequence verifiable units](../vendor/pstack/skills/principle-sequence-verifiable-units/SKILL.md). Their Cursor-specific tools are translated in [host compatibility](compatibility.md#coordination-translations). Repository policy, owner decisions and this procedure take precedence.

## 1. Frame the program with the owner

State, once, before any worker starts:

- The program objective and a countable done condition, for example "these three outcomes are merged, each with its required application evidence at the merged revision."
- The units. One unit is one coherent objective delivered as one PR with its own evidence. Name dependencies between units.
- Limits: at most three concurrently running workers unless the owner sets another number, the agents and models to use, wall-clock or spend limits, and the merge/release policy already authorized for the repository. Unless the owner names models, apply [model selection](models.md), which checks current session and weekly usage for each account.

Run the product interview for each substantial feature before its worker starts, reusing settled answers. A worker cannot interview the owner mid-flight without stalling, so unresolved product choices are settled here or parked as gates. Reversible preparation can proceed while the owner reviews the framing.

If one session could finish the work inside the budget, say so and do it in one workspace.

## 2. Resolve uncertainty before writing tasks

- An open visual, interaction or empirical question gets a throwaway [prototype](../vendor/pstack/skills/poteto-mode/playbooks/prototype.md) first. Keep its scratch path, revision and screenshots or observed output. The prototype informs the decision and does not ship.
- A contested module shape or a hard-to-reverse boundary gets [architect](../vendor/pstack/skills/architect/SKILL.md) in the coordinator's workspace before implementation units are cut.
- A shared API, schema or data contract lands as its own first unit. Dependent units start after it merges, or stack on its branch with the order recorded.

Product or preference choices that no prototype settles go to the owner with options and a recommendation.

## 3. Keep one durable program record

Cloud workspaces can disappear, so program state cannot live only in the coordinator's chat or scratch files. Use the repository's existing tracker. If it has none, open one GitHub issue per program, titled `Program: <outcome>`, and link it from every unit PR. Record:

- **Standing orders.** Numbered constraints that apply to every worker, such as delivery policy, forbidden paths, shared-resource rules and escalation rules. When you restate an instruction to a worker, add it here first.
- **Units.** One row per unit: objective, dependencies, owned paths, workspace link, session id, agent, model and effort with the reason for any fallback, branch, PR, current head SHA and state (`planned`, `running`, `blocked`, `in-review`, `verified`, `merged`, `abandoned`).
- **Verification ledger.** One row per PR and head SHA: the evidence scopes observed, links and verdict (`verified`, `partially-verified`, `blocked`, `failed`). A new head SHA voids the previous verdict for that PR.
- **Gates.** Each owner decision needed, its options, the recommended default and which units wait on it.

Each unit's detailed objective contract lives in its own task record or PR, per the [verification contract](verification.md#objective-contract). The program record links to it rather than duplicating it.

## 4. Write a complete task contract per unit

The initial message is the worker's whole context. A worker cannot see sibling workspaces or this chat. Write every field; an empty field means the unit is not scoped yet, so do not launch it.

```text
OBJECTIVE      One sentence a stranger can execute, with the customer outcome.
DECISIONS      Owner decisions, recorded assumptions, and questions that are out of scope for this unit.
SCOPE          Paths this unit may change; paths it must not change; its branch name.
CONTEXT        Links to the program record, task record, relevant files and PRs. Paste upstream unit results it depends on.
ACCEPTANCE     Observable criteria, one per line, with required evidence scopes.
VERIFY         Exact commands, application journey and environment; known limits of each.
SHARED         Accounts, databases, ports, previews and services, and whether this unit may mutate them.
LIMITS         Time or spend cap; on reaching it, push work, report partial results and stop.
FORBIDDEN      No force-push, no edits to other units' branches, no base-branch push, no work outside SCOPE.
DELIVERY       Ready-for-review PR to the base branch, linked to the program record; auto-merge policy for this unit.
REPORT         Status, branch, head SHA, PR, each criterion's result and evidence, deviations, blockers, follow-ups.
STANDING       The standing orders, pasted verbatim.
```

Size the contract to the unit. A one-line fix can be a short paragraph that still names the objective, scope, verification and report.

## 5. Launch workers

Before the first launch, confirm the starting branch contains the jfactory adoption commit and that the repository's cloud setup script prepares dependencies. Otherwise the worker starts without these instructions or tools.

Pilot one unit through the whole path, from contract to verified PR, before launching the rest when the unit shape is new. Correct the contract template and verification recipe from what the pilot reveals. For near-identical, cheap units, the first unit serves as the pilot.

Before each launch batch, choose every unit's tier and run the usage reader under [model selection](models.md) for the model to launch. Launch each independent unit in its own workspace:

```sh
conductor workspace create --repo-url <repository URL> --branch <base branch> \
  --name "<unit name>" --agent <agent> --model <model> [--effort <level>] --message-file <contract file> --json
```

Record the returned workspace link and first session id in the program record. Use `conductor session create` only for a second agent that should share an existing workspace's files, such as a reviewer. Two writers in one checkout are not isolated. Refill the running window as units finish instead of waiting for a whole batch.

## 6. Monitor by evidence, not by interrupting

Check state read-only at natural points: after a critical step, on a scheduled wakeup, and before reporting to the owner.

- `conductor session status <session>` for whether the worker is running or idle.
- `conductor session message <session> --after <last seen message id>` for its latest report or question.
- `gh pr list`, `gh pr view <number> --json headRefOid,state,statusCheckRollup,body` and pushed branches for actual output.

Do not send a message to check progress. A message starts another turn and can redirect the worker. Send one with `conductor message create --session <session>` only to answer a question, deliver a changed dependency or correct scope, and restate the relevant standing orders when you do. Use the host's scheduled wakeups with a long fallback interval rather than tight polling.

Answer worker questions from recorded decisions when possible. Otherwise park a gate, route the worker to independent in-scope work, and batch gates for the owner.

## 7. Verify each result independently

A worker's report is a claim. At the PR's current head SHA, inspect the criteria, the checks that ran, the application evidence and whether the assertions prove the claim. Record the verdict in the ledger. CI status is an input, not a verdict.

For expensive, judgment-heavy or high-risk units, launch a separate reviewer session or workspace to verify. Use the frontier tier from [model selection](models.md) and prefer the model from a different family than the worker when that account has usage remaining; otherwise disclose that the review was same-family. A failed verification becomes a fix task for the worker, not a re-run of the same check.

## 8. Integrate continuously

Land verified units as they finish rather than at the end. Follow [PR delivery](delivery.md), [worktree coordination](worktrees.md#deliver-and-integrate) and [auto-merge setup](auto-merge.md). Queue protected auto-merge only for a unit whose required evidence passed at its current head and whose owner gates are settled. For overlapping units, merge one at a time. After each merge, have dependent workers update from the base, rerun affected checks and report a new head SHA. A conflict-free merge is not proof of combined behavior.

The coordinator does not force-push, retarget or close another worker's PR. Those actions are worker tasks or owner decisions.

## 9. Recover from failures and interruptions

- **Stalled or failed worker.** Check its last message, branch and PR. A worker stopped by a usage limit continues on the fallback model as described in [model selection](models.md#3-decide-record-and-revisit); that is not a failed attempt. Otherwise retry once with a narrower contract or a different model when the failure mode warrants it. After two failed attempts, abandon the unit, record why and replan around it.
- **Late or duplicated output.** Reconcile it against the current base, program record and ledger before accepting anything.
- **Program-wide failure.** When further launches would repeat the same failure, add a stop line at the top of the standing orders, let running workers finish, fix the cause and then clear the stop line.
- **Coordinator interruption.** A new coordinator session follows [session pickup](../vendor/pstack/skills/poteto-mode/playbooks/session-pickup.md): read the program record, then `conductor workspace list --repo <repository> --include-archived --json`, each unit's session status and `gh pr list`. Resume from that state without relaunching finished units.
- **Owner-requested pause.** Follow [pause safely](../vendor/pstack/skills/poteto-mode/playbooks/pause-safely.md): tell workers to stop at a safe boundary and push their work, then update the program record with the resume point.

## 10. Escalate and close

Ask the owner only for product or preference decisions that no experiment settles, irreversible or unauthorized actions, standing orders that contradict observed reality, and dead ends that survived a replan. Batch these questions and keep routine retries, CI triage and merge mechanics out of them.

Close when every unit is `merged` or `abandoned` with a reason. Confirm the done condition on the merged base, including required application evidence. Archive only workspaces whose work is pushed or intentionally abandoned. Report the done condition, units and PR links, verdicts at merged SHAs, what was abandoned and why, remaining gates and the program record link. Add recurring corrections to the standing orders template or an enforced check.

## What this does not provide

These are instructions for an active coordinating agent, using Conductor's CLI and GitHub. jfactory does not install a background supervisor, scheduler or webhook. Nothing launches until an agent follows this procedure on request. Conductor routines can trigger agents from webhooks when the owner configures one separately. This procedure has not yet been evaluated end to end across models.
