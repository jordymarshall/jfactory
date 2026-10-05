# Coordinate several workspaces

Use this procedure when the owner asks one agent to deliver several objectives through separate Conductor workspaces, or when a program would outlive one session. One objective that fits a single session stays in one workspace under the normal jfactory loop. Parallel workspaces multiply cost and integration work; start them only on the owner's request or explicit agreement.

**Parallel work is this procedure, never in-session subagents.** When the owner asks for several objectives at once, or to "launch agents", "parallelize" or "finish all of this with agents", or says "use jfactory" for work that splits into independent units or is too big for one session, the coordinator runs `init`, `add`, a `brief` per unit and `launch`, so every worker is a visible Conductor workspace in the program's sidebar section. Do not substitute Task or Agent tool subagents, background helpers or worktrees inside the coordinator's own session for workers: the owner cannot see or message them, they share one machine's CPU and memory, and they bypass the program issue, the task contract, the model policy and independent verification. Subagents remain fine for read-only research or a short helper step inside the coordinator's own unit. If units already started as subagents, have each push its work and post a handoff comment on its PR, then stop the old writer and relaunch it with `launch --branch <pushed-branch>`; the brief names the PR and handoff. Read back the remote head before stopping the old writer.

**Watch model usage while workers run.** Read `usage.py` before each launch batch and about every five minutes while workers run. Compare the trend with the reserve in [model selection](models.md). Switch to the role's fallback before the next reading would cross that reserve. Record the reading and forecast with `--fallback --reason`.

Preserve running work before a model switch:

1. Ask the worker to finish its current safe step, commit, push and report its branch, head and handoff.
2. Read back the remote head. If it differs, preserve the remaining work before continuing.
3. Wait for the worker to go idle. Cancel only after its pushed checkpoint is confirmed.
4. Archive its workspace, then mark the unit `blocked` with the usage reason.
5. Run `launch <issue> <unit> --resume --branch <pushed-branch> --brief <handoff> --fallback --reason "<reading and trend>"`.

`--resume` requires a reported head, an idle previous session and an archived previous workspace. It preserves the failure-attempt count, including at the retry limit. A normal failed-attempt retry still counts. Keep one writer per branch. If a constrained worker cannot push, recover its files before cancellation or archival. Keep the remaining allowance for the coordinator and cross-family verification.

There are three roles:

- **Owner.** Decides outcomes and product questions, supervises through the program issue and the coordinator's chat, and can stop everything with one label.
- **Coordinator.** The agent the owner asked. It frames the program, writes task contracts, launches and monitors workers and verifiers, merges verified results and reports. It does not edit a worker's files; code changes and conflict resolution are worker tasks.
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
| `launch <issue> <unit> --brief FILE [--dry-run] [--stack-on UNIT] [--branch BRANCH] [--allow-overlap] [--resume --reason] [--fallback --reason] [--agent/--model/--effort]` | Coordinator | Creates the unit's Conductor workspace with the policy's agent and model, moves it into the program's sidebar section, after checking hold, concurrency limit, the repository limit across programs (`repo_limit`), path overlap with running units, that `--branch` exists, dependencies, open decisions, brief completeness, attempt limit, model availability and reviewer model family |
| `launch --role verify\|build\|fix --pr N --message-file FILE [--branch] [--project-id] [--agent/--model/--effort] [--dry-run]` | Anyone launching an agent for one PR | Creates a workspace named `<role>-<repo name>-<PR number>`, such as `verify-loopcraft-102`, from the PR's head branch unless `--branch` says otherwise, and prints its id. It uses the repository's Conductor project when one matches, otherwise the repository URL. `verify` defaults to the verify tier (GPT Sol 6.1 at low effort, pinned), `build` and `fix` to the frontier tier. It refuses any other role, and a `--name` that breaks the convention. See [finished workspaces archive themselves](#finished-workspaces-archive-themselves) |
| `report <issue> <unit> --state ...` | Worker | Posts a structured comment with its state, PR, head SHA, note or question |
| `sync <issue> [--dry-run]` | Coordinator | Folds worker reports, PR state and session status into the issue, voids verdicts on new heads, turns a failed or blocked verdict at a unit's head into its next step (a fix task when the cause is the change, an owner decision the unit waits on when the cause includes the rules) and lists units ready to launch, including verifiers whose target has a PR (with the `--stack-on` to use) |
| `verdict <issue> <unit> --head --verdict --scopes --evidence --verifier [--full] [--features] [--since] [--screenshots] [--standards] [--walkthrough] [--cause --rule-change] [--rule-decision]` | Verifier | Records verification only at the PR's current head, requires every declared scope and a cause for a failed or blocked verdict, routes it like `sync` does, and posts the PR verdict that the `jfactory verified` status reads. The implementer is the unit's launched model, so units launched outside the tool cannot be verified through it |
| `merge <issue> <unit>` | Coordinator | Queues protected auto-merge pinned to the unit's current head. It needs a `verified` verdict at that head, unless the base branch's mapping makes the change CI-only (every affected feature `verify: ci`, with no screens, tests or agent instructions changed); then GitHub's required CI is the gate. It also needs no open decisions, and a recorded `merge_deploys` of `staging` or `none` |
| `gate add` / `gate resolve` | Coordinator | Records an owner decision and its answer; open decisions block launch and merge for their units. A rule-change decision is resolved with `--decision change-rule` or `keep-rule`, which sets the waiting unit's next step |
| `set <issue> <unit> --state` | Coordinator | Marks a unit blocked, failed or abandoned with a note |
| `close <issue>` | Coordinator | Closes the program only when every unit is merged, done (verifiers without their own PR) or abandoned |
| `tidy` | Anyone | Archives finished PR workspaces and deletes finished `Program:` sidebar sections |
| `land --pr N [--head SHA] [--wait MIN]` | Anyone delivering a verified PR outside a program | Queues protected squash auto-merge at the verified head, waits for GitHub to merge it (30 minutes by default), reads back the merge commit, then archives that PR's finished workspaces, giving their sessions up to two minutes to go idle. On every read it compares the PR's head with the verified one: if the head moves while queued (a push by someone with write access keeps auto-merge queued), it cancels auto-merge and asks for a new verification. If auto-merge is removed, it stops. If the PR merged at a different head, it archives and then reports that what merged was not verified |

`sync`, `verdict`, `merge`, `land`, `launch`, `close` and `tidy` also archive finished PR workspaces as they run; see [finished workspaces archive themselves](#finished-workspaces-archive-themselves).

The issue body has one writer, the coordinator. Workers never edit it; they add report comments, and the newest report after the coordinator's last change to that unit wins at the next `sync`. This avoids concurrent edits to one body. Anyone with comment access could post a report, so the coordinator still checks each claim against the actual PR.

The tool is a guard, not a supervisor. It runs only when an agent calls it, and it does not judge whether evidence is meaningful.

## The agent hub

When the owner asks for one agent to talk to, that session runs the [agent-coordinator skill](../skills/agent-coordinator/SKILL.md) and becomes the **agent hub**. The hub is recorded in one pinned issue, "Agent hub" (label `jfactory-hub`). Coordinators send it messages tagged `QUESTION`, `BLOCKER`, `RISK`, `MILESTONE` or `DIGEST` (routine progress, at most one every 30 minutes). Workers never message it: the launch footer tells them to report only to their coordinator, and the hub redirects any worker that does. `coord.py sync` prints the current hub, and records the session that runs it as the program's coordinator, so the hub can find every coordinator.

## Model policy

Each unit has a role, and each role is one tier of [model selection](models.md). The tool builds its roles from the same table as the usage reader, so the two cannot drift:

| Role | Tier | Use |
| --- | --- | --- |
| `implement` (default) | Frontier | Features, fixes, prototypes and other code changes that need strong judgment |
| `fast` | Fast | Well-scoped routine edits, follow-up fixes with a known cause, CI triage |
| `trivial` | Trivial | Renames, copy and formatting changes, lookups |
| `verify` | Verify | Verification, review and PR follow-through for another unit, always from a different model family than its implementer |

Use `launch --fallback --reason "<usage reading>"` when the primary has no usage remaining or a recorded forecast will cross its reserve before the next reading; the reason is recorded on the unit. A verifier's family switch after Codex implementation happens automatically and is recorded as `alternate`, not as a fallback.

Every role chooses effort per unit by difficulty, from `low` to `high` (default `medium`). Use `low` for mechanical edits and narrow checks, `medium` for ordinary features and reviews, and `high` for ambiguous, cross-cutting or high-risk work. Set it with `add --effort` or `launch --effort`; the tool refuses levels outside the role's range. Raise effort on a retry when the previous attempt failed from difficulty rather than a bad contract. The exceptions are Opus 5.5 as a fast or trivial model, which always runs at `low` effort, and every verifier, which runs at the verify tier's `low` effort (GPT Sol 6.1 in standard mode): the tool applies these whatever the unit's effort, and refuses `launch --effort` with another level.

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

- The program objective and a countable done condition, for example "these three outcomes are merged, each verified as right (criteria, job goals, standards and outcomes) with its required application evidence at the merged revision."
- The units. One unit is one coherent objective delivered as one PR with its own evidence. Name dependencies and each unit's owned paths.
- Each unit's verification standard: its acceptance criteria and the evidence scopes that define verified (`add --requires`, such as `application,unit`). Application evidence comes from the PR preview or staging. Workers loop until the standard passes; the coordinator merges without asking again once it does.
- The concurrency limit (default three) and the repository-wide limit across all open programs (`repo_limit` in `.jfactory/coordination.json`; `launch` refuses beyond it). Every running worker pushes into one CI queue, so size `repo_limit` to the CI runners, not to the work available ([queue operations](ci-runners.md#queue-operations-fewer-jobs-before-more-machines)), the model policy (see [model selection](models.md), including the usage check before each launch batch), wall-clock or spend limits, and what merging deploys (`init --merge-deploys` or `.jfactory/coordination.json`). `merge` refuses unless merges reach staging or nothing; production releases stay a deliberate owner action.

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

### Separate workspaces, separate files

Every worker gets its own Conductor workspace: its own machine, checkout and branch, so no two workers share a working copy. Merge conflicts come from two workers editing the same files. Prevent them when you plan, not when you merge:

- **Give every unit `--paths`** (`add --paths 'app/library/**,app/lib/library/**'`): the files it may change. Split units by file ownership, not only by feature.
- **`launch` refuses a unit whose paths overlap a running unit's**, in this program or any other open one. Sequence it (`--depends`), stack it on the other unit's branch (`--stack-on`), or pass `--allow-overlap` and name in both briefs which files each worker owns.
- **Put shared files in one unit.** Shared primitives, tokens, schema and config belong to one foundation unit that merges first; page units depend on it.
- **Workers stay mergeable.** The launch message tells each worker to merge the base into its branch before every push and whenever told the base moved (no rebase, no force-push), resolve conflicts itself and rerun the affected checks. After each merge, `sync` names the running units whose paths the merge touched; message those workers to update.

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

### Waiting budget

Every check spends tokens, and a check that finds nothing new moves nothing. These limits apply to every agent, coordinator, worker and verifier alike:

- **Wait on events, not loops.** Prefer a notification, a background watch or one blocking command with a deadline (for example `coord.py land --wait`) over repeated status checks. Each check is a model turn.
- **At most 5 checks per wait.** If polling can't be avoided, space checks at least 5 minutes apart and stop after 5 that find nothing new. `sync` enforces this for coordinators: the fifth quiet sync in a row prints `Stop:`.
- **The same failure twice means stop.** Investigate once. If the second attempt fails the same way, report the blocker with its evidence; never retry the same thing in a loop.
- **No progress means stop.** When 5 checks, or 30 minutes of waiting, show no change, report what each unit is waiting on and the one step that would unblock it, then end the turn.
- **Don't launch into a stall.** While sessions are idle, failing or out of usage, launch nothing new; pause and report.
- **Reviews are bounded too.** A `review`-level change gets one review and one re-check; a failing `independent` change gets new investigation, not identical retries.

Resume only when a session, a PR or the owner reports something new.

### The stuck-PR check

Do not depend on a loop inside one agent chat to watch PRs. The chat ends, and the PRs then wait unseen. A scheduled workflow ([template](../templates/jfactory-pr-health.yml)) runs `scripts/pr_health.py` every 30 minutes. It uses no AI model. For each open PR into the default branch, it finds the state and the one next step:

| State | Next step |
| --- | --- |
| `conflict` | The author merges the base branch and resolves the conflicts. |
| `ci-failed` | The author fixes the failing check. An infrastructure failure gets one automatic re-run per head. |
| `partial` | The latest verdict at the head is `partially-verified`, `blocked` or `failed`. The table quotes the first line of its evidence and names who acts. |
| `behind` | A verified PR gets the base branch merged in automatically, once per head, one PR at a time (oldest first, a merge train: [queue operations](ci-runners.md#queue-operations-fewer-jobs-before-more-machines)). The verifier then re-checks only the merge with `--since`. |
| `needs-verdict` | CI is green for more than 1 hour, and no verdict exists at the head. The verifier posts one. |
| `gate-failed`, `not-queued`, `no-ci`, `idle` | The table says what is missing. `idle` means no commit, check or comment for more than 6 hours. |

The check keeps one issue labelled `jfactory-pr-health` with the title "Stuck PRs". It edits the issue in place and never comments. It closes the issue when no PR is stuck and reopens it when one is. Read that issue, not a chat, to see what waits on whom. The check never re-runs a test failure, never merges a PR and never changes code. Run it by hand without `--act` to see the table without changing anything.

For detail, read `conductor session message <session> --after <last seen message id>` and the PR. Do not send a message to check progress; a message starts another turn and can redirect the worker. Send one with `conductor message create --session <session>` only to answer a question, deliver a changed dependency or correct scope, and restate the relevant standing orders when you do.

A worker question becomes an open decision at `sync`. Answer it from recorded decisions when possible with `gate resolve` and a message to the worker. Otherwise batch it for the owner.

## 7. Verify each result independently

A worker's report is a claim; the verify unit checks it at the PR's current head and records the result with `verdict`. CI status is an input to that verdict, not a substitute for it. For a unit the plan calls CI-only (every changed feature `verify: ci`, with no screens, tests or agent instructions changed), still check the claim against the PR, but no verdict is needed: `merge` relies on GitHub's required CI. A new head voids the previous verdict at the next `sync`.

Every unit whose PR touches an `independent` (high-risk), unmapped or gate path gets one `verify` unit that depends on it (a CI-only unit, as the plan decides, needs none). The verify unit is launched with `--stack-on` so it checks out the PR branch once the worker reports `in-review`. Its contract asks it to:

- run `verify_plan.py smoke` for the target first and report a failed step as `blocked`;
- check the PR as the [verification contract](verification.md#change-aware-verification-and-the-merge-gate) describes: reuse green CI, drive the changed journeys when users see the change and review screenshots of each changed screen with a vision-capable model (linked with `--screenshots`), walk each changed journey step by step, looking at the screen after every action (linked with `--walkthrough`), check the change against the standards map and the feature's journey (named with `--standards`), score judgment criteria, and review the diff and any mapping change;
- post the verdict itself with `coord.py verdict`, and follow the PR through CI and review comments.

The verifier produces everything the gate requires for the plan. For changed screens, that is the walkthrough and the reviewed screenshots. An instruction to keep the review cheap limits extra work. It never permits `partially-verified` when the required proof is possible. Use `partially-verified` or `blocked` only when the proof is really blocked, for example by missing access or a missing environment, and name the blocker in the evidence. A brief that says "walkthrough only if cheap" is wrong; write "the proof the gate requires, nothing more".

It does not change product code. Each failed or blocked verdict names its cause, as [the verification contract](verification.md#change-aware-verification-and-the-merge-gate) describes. Defects in the change (`--cause change`) become a fix task for the original worker, and after the fix the same verifier re-checks only the changes with `--since`. A rule the verifier says is wrong (`--cause rules`, or `both`) becomes an owner decision instead: the unit is `blocked` on it, and `launch` and `merge` refuse until the owner answers. Bring it to the owner with the verifier's recommendation. If they approve the change, add a unit for the rule change (its own PR, verified like any other) and re-verify the original PR under the new rule once it merges. If they keep the rule, `gate resolve --decision keep-rule` turns the unit into an ordinary fix task. Either way the next verdict links their answer with `--rule-decision`. Never resolve a rule-change decision from the coordinator's own judgment. The coordinator does not re-inspect a posted verdict; it merges verified units.
It runs on GPT Sol 6.1 at low effort, or Opus 5.5 at low effort when the implementer ran on Codex; see the verify tier in [model selection](models.md). A verifier launched for a PR outside a program uses `launch --role verify --pr <number>`; either way its workspace is archived automatically once it is finished, so nobody archives it by hand.

## 8. Integrate continuously

Land verified units as they finish rather than at the end. Follow [PR delivery](delivery.md), [worktree coordination](worktrees.md#deliver-and-integrate) and [auto-merge setup](auto-merge.md). `merge` queues protected auto-merge pinned to the unit's current head: after a `verified` verdict at that head, or, for a unit the plan calls CI-only and that no verdict has failed at that head, on GitHub's required CI. The unit must still be right; CI is its evidence, and a failed, blocked or partial verdict at the head refuses the merge. For overlapping units, merge one at a time. After each merge, message dependent workers to update from the base, rerun affected checks and report the new head. A conflict-free merge is not proof of combined behavior.

Finished workspaces are archived as soon as their unit finishes, not at program close, so the sidebar shows only live work. `sync` archives the workspace of every `merged`, `done` or `abandoned` unit once its session is idle, records it on the unit and reports sessions still working. Set `abandoned` only after the unit's work is pushed or deliberately discarded. `--keep-workspaces` skips archiving.

### Finished workspaces archive themselves

Conductor records no branch or PR on a workspace and has no archive-on-merge, so jfactory names every workspace it launches for a PR `<role>-<repo name>-<PR number>` (role `verify`, `build` or `fix`) with `coord.py launch --role <role> --pr <number>`. The name is how a later command finds the PR.

jfactory-launched workspaces are archived automatically, the next time any of `sync`, `verdict` (in `coord.py` or `verify_plan.py`), `merge`, `land`, `launch`, `close` or `tidy` runs after their PR merges or closes. GitHub merges a queued auto-merge later, on its own, so a sweep that runs when the merge is queued still finds the PR open. That is why a verified PR outside a program is delivered with `land`: it waits for the merge to land and then archives. A program's `sync` and `close` run after merges anyway. Every `launch` also sweeps, as a safety net for a merge that landed after the last command. Each of these lists your own (`--mine`) workspaces and archives one only when all of these hold:

- its whole name is exactly `<role>-<repo name>-<PR number>`: a lowercase role of `verify`, `build` or `fix`, the repository's name (in any letter case, as GitHub treats it), and a PR number without leading zeros. Nothing may come before or after it, not even a space or a newline;
- its repository URL, as an HTTPS, SSH or `git@host:owner/name` remote, is exactly this repository on GitHub: same host, owner and name, with nothing extra in the path;
- GitHub reports that PR as merged or closed;
- every session in it, read across every page of Conductor's session list, reports `idle`, the only status Conductor gives a stopped session. A session that is `working`, or whose status is missing or unrecognised, keeps the workspace; so does a session list jfactory cannot read completely, including a page that is not the one asked for or that repeats sessions;
- it is not the workspace the command runs in.

It reports what it archived and each finished workspace it kept, with the reason; a later run archives those once they are idle. Anything else is left alone, so the owner's workspaces, other people's and other repositories' are never touched.

- **It cannot break or hold up the command.** Every call site gives the sweep the same 5-second budget. At the limit it stops and prints one line, and the next command continues where it left off. A verdict is posted before the sweep starts, so the sweep adds at most a few seconds to it. Without the `conductor` CLI, such as on a CI runner, it does nothing. Without `gh`, or when `gh` or Conductor fails, it prints one `Check:` line for the whole sweep, not one per workspace, and the command carries on.
- **Archiving is reversible.** Conductor's CLI archives workspaces; it does not delete them. Archived workspaces stay listed under `conductor workspace list --include-archived`.

Archive by hand only a workspace launched outside the convention, such as a usage probe or one created directly with `conductor workspace create`: `conductor workspace archive <workspace id>`, once its work is finished. Archive only workspaces you created for this work. Leave the owner's own workspaces and other coordinators' workspaces alone, even when they look idle.

The coordinator does not force-push, retarget or close another worker's PR. Those actions are worker tasks or owner decisions.

## 9. Recover from failures and interruptions

- **Stalled or failed worker.** Read its last messages, branch and PR. A worker stopped by a usage limit has not failed: continue it on the role's fallback per [model selection](models.md#3-decide-record-and-revisit), which does not count toward the attempt limit. Otherwise, mark it `failed` with the reason and relaunch once with a narrower contract or another model when the failure warrants it. `launch` refuses a fourth attempt; abandon the unit with `set --state abandoned --note` and replan around it.
- **Late or duplicated output.** Reconcile it against the current base, program issue and ledger before accepting anything.
- **Program-wide failure.** When further launches would repeat the same failure, add the hold label, let running workers stop safely, fix the cause and remove the label.
- **Coordinator interruption.** A new coordinator session follows [session pickup](../vendor/pstack/skills/poteto-mode/playbooks/session-pickup.md): `list`, read the program issue, then `sync`. Resume from that state without relaunching finished units.
- **Owner-requested pause.** Add the hold label and follow [pause safely](../vendor/pstack/skills/poteto-mode/playbooks/pause-safely.md) for the coordinator's own work.

## 10. Escalate and close

Ask the owner only for product or preference decisions that no experiment settles, irreversible or unauthorized actions, standing orders that contradict observed reality, and dead ends that survived a replan. Batch these questions and keep routine retries, CI triage and merge mechanics out of them.

Confirm the done condition on the merged base, including required application evidence, then run `close`. It archives any remaining finished workspaces, deletes the program's sidebar section once none of its sessions is still working, and runs `tidy`. `tidy` deletes any other `Program:` section whose workspaces are all archived, or whose program issue is closed and none of whose remaining workspaces is still working. `close` never lets `tidy` delete its own section while one of its finished workspaces is unarchived. It never touches sections without the `Program:` prefix, and can run on its own. Before reporting, check `conductor workspace list --mine --repo <repository> --json` for anything the program launched outside the tool and its naming convention, and archive those by hand. Ask before archiving the coordinator's own workspace, which the owner may still be reading. Leave the owner's other workspaces and other coordinators' workspaces alone. Report the done condition, units and PR links, verdicts at merged SHAs, what was abandoned and why, remaining decisions and the program issue. Add recurring corrections to the standing orders template or an enforced check.

## What this does not provide

jfactory does not install a background supervisor, scheduler or webhook. Nothing launches or syncs unless an agent runs the tool, so a coordinator session that stops leaves workers running unsupervised until someone resumes it. Conductor routines can trigger agents from webhooks when the owner configures one separately. The tool's rules are tested against simulated `gh` and `conductor`; an end-to-end program with real workers has not yet been evaluated.
