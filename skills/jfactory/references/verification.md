# Verification contract

Choose evidence from the claim, not from whichever test is easiest to run.

**Done means right.** A change is done only when it is right: it serves the outcomes in `outcomes/README.md` and crosses none of its non-goals, keeps every standing goal of the jobs it touches (`outcomes/<job>.md`), meets the standards map (`.jfactory/standards.md`) and meets its own criteria, each proven at the current commit. Green CI, passing tests, an approved review or a completed checklist is evidence toward done, never done by itself. Done but not right is not done: keep working, or report it as not done.

Engineering correctness, experience quality, customer value and agent-workflow effectiveness need different evidence, and each one that applies must hold. Proving one does not stand in for another: correct code with a confusing experience, or a polished screen that doesn't serve the outcome, is not done.

## Objective contract

Write the objective before substantial implementation, in the task location named in the setup record (usually the GitHub issue for the work; for a small fix, the PR description). [templates/objective.md](../templates/objective.md) has the fields. Keep one canonical acceptance record and update it as work progresses; link machine-readable tests/criteria to it when useful. It contains:

- Customer and experience outcome, with owner decisions, agent assumptions and unsettled questions distinguished.
- Scope and non-goals, including constraints and dependencies on other PRs.
- Observable criteria. For each, give the starting state, user action, expected result, independent side-effect/readback check, required scopes and the command or manual observation that can prove it. A missing test is work to implement, not a reason to remove the criterion.
- Execution target, account/data ownership, permitted side effects and any cost/time limits. Note access still needed.
- Review/checkpoint and stop conditions. Carry forward the agreed merge/release policy; identify choices that still need owner judgment.
- Current criterion results, evidence links/revision, unresolved blockers and next action for a resumed session.

For example, "make saving good" is incomplete. "A signed-in customer saves an item, sees it after reload and in a new session, and receives a recoverable error if saving fails" identifies observable behavior. The tests must exercise the real application's auth/storage boundary for that claim. An additional customer interview may still be needed to determine whether saving solves the right problem.

Work through unresolved criteria, and anything that is not yet right against the job goals, standards and outcomes, autonomously. Use failed checks and observations to choose the next correction. Keep the original acceptance standard visible when a proposal changes it; an agent cannot mark a requirement done by deleting its failing assertion. Stop dependent work for a material unresolved decision, inaccessible required service or exhausted agreed budget; continue feasible independent work. Once criteria and required reviews pass, deliver under the recorded PR policy and stop at the agreed boundary.

## Required scopes

| Scope | What it can demonstrate |
| --- | --- |
| unit | A function's behavior under the stated inputs |
| component | A real UI component with explicit substituted boundaries |
| integration | Selected real subsystem interactions, such as a disposable database |
| application | The real application entry point, navigation/auth where applicable, action, resulting state and relevant side effects |
| provider | Behavior against the identified real external service |
| deployed | Behavior on the identified deployed revision/environment |
| static | Documentation, type, lint, build or structural checks, as identified |
| judgment | An independent reviewer from another model family scored the result against a rubric agreed before building, citing the artifacts it inspected |

Use `judgment` for criteria no test can decide, such as "a first-time user can find the save control" or "the error message explains how to recover". Write the rubric in the objective before building: observable points, what the judge inspects (screenshots, walkthrough video, the running preview, copy) and the pass mark. The independent verifier scores it at the PR head and names what it looked at. A judgment verdict counts toward `verified` and auto-merge like any other scope. It is still an assessment: label it as one in the handoff. It never replaces a deterministic check where one is possible, and it is not owner or customer acceptance.

These are different claims, not a ladder where one automatically proves all others. A changed signed-in save journey normally needs application evidence with independent storage readback. A real-provider requirement also needs provider evidence. A library/CLI should exercise its actual public interface, not invent a browser requirement. Documentation-only edits can use static checks.

Choose the cheapest scope that can prove each claim. A browser journey is required only for a criterion about what a user sees or does in the running app, and then only the journeys the change can affect. A server-side fix, a refactor covered by tests or a copy change in one component does not need the whole end-to-end suite. See [proportional cost](#keep-each-pr-proportional).

Record expected state before execution, the actual user action/command, observed result and independent side-effect observation. Check reload/readback, access boundaries, retries, idempotency, failure recovery and downstream handoffs where the objective requires them. Screenshots complement assertions; a success toast alone does not prove persistence. Tests may stub isolated external boundaries, but then they cannot prove those external systems worked.

Capture the code revision and dirty source identity, exact command, environment identity without secrets, assertions/results and durable evidence links. Keep failed attempts. Ensure cleanup preserves evidence and only removes owned instances/test data. Negative controls should demonstrate that a broken behavior or failed command cannot be reported as passed. Do not weaken assertions, skip a failing check or edit expected outputs just to obtain green results.

## Change-aware verification and the merge gate

Verification needs follow from what a PR changes, not from a fixed repository-wide check. The repository's `.jfactory/verification.json` links code paths to the project verifier's feature-map entries and to CI suites (see [the example](../templates/verification.example.json)). Setup creates it with [the guided mapping procedure](mapping.md), and `verify_plan.py audit` (run by `ci` on every PR) keeps it current: a PR that adds or removes an area maps it in the same PR.

1. **Plan.** `python3 <skill>/scripts/verify_plan.py plan --base origin/<base>` lists the affected features with their recipes and the CI suites to run. Changed files that match no feature or static pattern require **full** verification of every feature, so `ci` refuses them until they are mapped. Any change to `.jfactory/`, `.github/workflows/` or `.github/rulesets/` needs a full verdict too, but runs only `always_suites` and `full_suites`, not every feature's journeys. Static patterns cover only files that cannot change runtime or agent behavior: never agent instructions, skills or verification recipes, which are Markdown too. Put the plan in the PR, alongside the objective's own acceptance criteria.
2. **Loop.** The implementer runs those recipes and the objective's criteria until they pass on the current head.
3. **Automated floor.** CI runs the suites the plan names. The [change-aware CI job](../templates/jfactory-checks.yml) runs `verify_plan.py ci`: it audits the map, fails on unmapped files, then runs each planned suite's command, starting the app's target around suites that need it. It adds suites that recorded coverage says execute the changed files, and splits the work across parallel jobs. It runs every suite with `--all` and records coverage when the owner's `full_suite` choice calls for a whole-suite run. A repository may build its own equivalent; `setup_check.py` fails when the map has journey suites but no workflow runs `verify_plan.py ci`.
4. **Risk level.** Each feature in the mapping has a `verify` level, agreed with the owner at setup.
   - **`independent`** (the default) needs the verdict in step 5.
   - **`ci`** needs only the passing CI suites. Use it only for changes that cannot alter what users see or do, what is stored, who can access what, money, or how the rules are enforced: internal refactors covered by tests, low-risk tooling, the model-usage reader.
   - **Always independent, whatever the level.** `plan` requires the verdict for any feature with screens users see, and for any change to tests or agent instructions at any depth. Tests include everything inside `e2e/`, `tests/`, `test/`, `__tests__/`, `spec/`, `cypress/` and `testdata/` folders (fixtures and helpers too), `*.test.*`, `*.spec.*`, `*.cy.*` and `*_spec.rb` files, and test-runner configs. A folder name can over-match ordinary code; that costs one extra review, which is cheaper than a gap. Agent instructions include `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `SKILL.md`, `.agents/`, `.claude/`, `.cursor/` and `.codex/` folders, and rule files such as `.cursorrules`. A PR must not be able to weaken a screen, a test or an instruction with only CI watching. Screens come from the map, not from file paths: a feature has screens when one of its suites has a `target` or it says `"screens": true`, so declare every screen feature. When such a file belongs to a `ci` feature, `audit` warns that the level is overridden. A static pattern never covers agent instructions or test code: such a file counts as unmapped and `audit` fails. Prose inside a test folder, such as `docs/spec/architecture.md`, may stay static.

   Anything that changes behavior users see (product and UX), data and storage, sign-in and permissions, payments, migrations, security, agent instructions and the enforcement scripts stays `independent`. A PR touching both levels needs the stricter one, and its verdict must cover the `independent` features. Unmapped files and gate files (`.jfactory/`, workflows, rulesets) always need a full verdict. That is also how a change that lowers a level gets verified: the level is read from the base branch, so a PR cannot lower its own. When unsure, choose `independent`.
5. **Independent verdict.** One verifier from a different model family (the default is GPT Luna 6 in fast mode) checks the PR at its current head and posts the verdict itself; nobody re-judges it afterwards. It does not repeat work CI already proved:
   - **Deterministic suites:** it reuses CI's results at the head instead of re-running them. `verdict --verdict verified` refuses while any CI check at that head is missing, running or failed, so the reuse is safe. It re-runs a suite only when it doubts what the suite's assertions prove.
   - **What users see:** when the PR changes anything users see, it drives the changed journeys in the running app (PR preview, staging or the local target) and captures screenshots of each changed screen at the target viewports (for example desktop and mobile), plus a walkthrough video for interactions and motion. It looks at them with a vision-capable model, against the objective: layout, readability, clipping, collisions, empty and error states, and whether the screen does what the criterion says. Scripted journeys prove structure and behavior, not appearance, so this is the only check that sees the screen. It runs `smoke` first. The verdict links the images with `--screenshots` (one per link, uploaded to the PR or the CI run's artifacts); for a `--since` re-check whose changes leave the screens untouched, link the earlier images again.
   - **Outcomes and standards:** it checks the change at every level. It checks the work item's own criteria. It checks the standing goals in the `outcomes/<job>.md` document of each affected feature, running or confirming each goal's proof and scoring its rubric. It checks the rows of `.jfactory/standards.md` the change touches: the writing rules for changed copy, the design system for changed screens, the UX principles for changed interactions, and the budgets and policies for everything else. And it checks the outcomes and non-goals in `outcomes/README.md`. It names every document it checked with `--standards <path>`; with a standards map, the command refuses a verdict on a change that isn't static without them, and the status rejects one.
   - **When a document and the product disagree:** it decides which is wrong. If the document is out of date because the product changed on purpose (an owner decision or an agreed objective), the PR must update the document; a PR that doesn't is `failed` until it does. If the product no longer does what the document says, that is a defect: `failed`, with the document and the observed behavior as evidence. Never accept a document edited to match broken behavior; an edit to a outcome or standards document must link the decision that changed the intent.
   - **Judgment criteria:** it scores them against their rubric.
   - **Everything else:** it reviews the diff and any mapping change, and checks each criterion without passing evidence at this head.

   It lists every criterion's result in the verdict's evidence and posts with `verify_plan.py verdict --pr <n> --head <sha> --verdict verified --verifier <agent/model> --implementer <agent/model> --evidence <link> [--screenshots <link> ...] [--full]`. After a `failed` or `blocked` verdict, the fix gets a delta re-check: `git diff <earlier head>..<new head>` and `verify_plan.py plan --base <earlier head>` show what changed. The verifier re-runs what that affects, confirms each earlier finding is fixed, and posts with `--since <earlier head>`. The status accepts `--since` only when a trusted verdict exists at that head, and CI must still be green at the new head. The command refuses a stale head, incomplete coverage, an identity whose model family it cannot tell, and a same-family verifier unless the mapping records the owner's `"allow_same_family": true`. A verified verdict on a change to screens users see (a changed file that isn't a test, an agent instruction or plain-text prose, in a feature with a journey suite that has a `target` or `"screens": true`; MDX counts as a screen, and an unmapped file that could render puts every screen in scope) must link reviewed screenshots; the command refuses one without them and the status rejects it. Set `"require_screenshots": false` in the mapping to opt out. Static-only changes need no independent verdict.
6. **Required status.** The [`jfactory verified` workflow](../templates/jfactory-verified.yml) re-evaluates on every push and comment. It uses `pull_request_target` and `issue_comment`, so GitHub loads the workflow from the base or default branch rather than the PR; it checks out only the base branch's script and mapping and never runs PR code. It sets the `jfactory verified` commit status. Any change that isn't static fails until the PR description starts with its objective: the first non-empty line is a heading that starts with the word Objective (any level, such as `## Objective`) or an `Objective:` line (bold allowed), followed by the objective or a link to its issue (the check confirms presence and minimal length, not quality); set `"require_objective": false` in the mapping to opt out. Otherwise, it passes on its own when the plan is static or CI-only (every affected feature is `verify: ci`, with no screens, tests or agent instructions changed). Otherwise it passes only for a trusted verdict comment at the current head that covers the plan's independent features, or every feature when full verification applies, and that links reviewed screenshots when the change touches screens users see. A new push resets it. Make it a required check next to CI.

### Keep each PR proportional

A PR should run every check its change can affect and nothing else, and finish quickly. Three parts of the mapping do this; [guided mapping](mapping.md) sets them up:

- **Selection by the map and by recorded coverage.** The map names each feature's own suites. Each whole-suite run records which files each suite executed (`ci --all --impact-out`), and a PR adds every suite that executed a changed file (`ci --impact`). Shared code therefore runs exactly the journeys that use it, without mapping it to every journey. Coverage only adds suites. A file it hasn't seen falls back to the map, and the whole-suite run covers anything coverage cannot see.
- **Parallel jobs.** `suites` records each suite's command, measured `minutes` and, for journeys, the `target` app it needs. `ci --shard I/N` splits the planned suites across `shards` CI jobs, balanced by minutes, so the wait is roughly the total divided by the job count.
- **No journeys on every PR.** `audit` fails when `always_suites` or `static_suites` include a suite with a `target`, and a gate-only change runs only `always_suites` and `full_suites`.

A time cap is optional. If the owner sets `pr_budget_minutes` (or a feature's `budget_minutes`), `plan` shows the estimate next to it and `audit` warns about changes over it. It never removes a required check. A required job that always runs every suite also meets the floor when the owner accepts its time. The owner decides at setup when the whole suite runs (`full_suite`: on request, nightly, on every merge or on every PR; see [guided mapping](mapping.md#8-set-risk-levels-and-when-the-whole-suite-runs)), because browser journeys cost time and compute. Run it [before a release](release.md#release-when-the-owner-asks) whatever the choice.

The same applies to the independent verifier. It checks what the plan and the criteria name, and drives the journeys the change touches, not the whole app. Before an application check it runs `verify_plan.py smoke --target <name>` (with `--url` for a PR preview). If a step fails, it posts a `blocked` verdict naming that step, and does not retry the journey until it times out. When a plan is full only because it changes gate files (the mapping, workflows or rulesets), the verifier reviews the gate change and runs the recipes of the features whose checks it alters, while CI runs the suites the plan names. Unmapped code still needs every recipe, which is one more reason to map every file.

These mechanics enforce coverage and freshness. They do not judge whether a recipe or assertion is adequate; reviewers still inspect the evidence. Verdict comments are trusted from repository owners, members and collaborators only.

## Optional deterministic receipts

The bundled `scripts/evidence.py` runs an existing check and records its exit status, output, timeout/cleanup, task hash and source fingerprint. Its `check` command rejects missing required scopes, failed/latest checks, missing or changed logs, and stale code/task evidence. It does not inspect browser behavior or determine whether a command/assertion is adequate. A trivial successful command is not meaningful verification. The agent/reviewer must inspect what the check actually proves.

Keep a stable acceptance file with the existing task; do not duplicate one already expressed in another machine-readable format just for this helper. Example for a repository that adopts these receipts:

```json
{"objective":"Edits survive reopening the saved item","criteria":[{"id":"save","expected":"Reopening displays the saved edits","required_scopes":["application"]}]}
```

From the target repository, with the installed skill's actual path:

```sh
python3 .agents/skills/jfactory/scripts/evidence.py run --task docs/tasks/save.json --criterion save --scope application --environment local-review-db -- npm run test:e2e -- save.spec.ts
python3 .agents/skills/jfactory/scripts/evidence.py check --task docs/tasks/save.json
```

A `judgment` criterion carries its `rubric` in the acceptance file, so the rubric is fixed before building (changing it makes earlier receipts stale). `run` refuses the `judgment` scope, because a passing command cannot prove one. The independent reviewer records its score instead:

```sh
python3 .agents/skills/jfactory/scripts/evidence.py judge --task docs/tasks/save.json --criterion clear --judge codex/gpt-6-luna --implementer claude/opus-5-5-1m --result pass --scores "1 yes; 2 yes; 3 yes" --inspected .context/ux/save/artifacts/save.png
```

`judge` refuses a judge from the implementer's model family, and inspected files that don't exist. It records a hash of each inspected file.

The runner uses `.context/jfactory/` for local evidence and excludes only that directory from its source fingerprint. Never put application source there. No credentials in command arguments or environment labels; review logs before sharing. Only evidence IDs, hashes and existing task records need be durable; publish selected sanitized artifacts when a PR reviewer needs them, not all local logs. The code fingerprint covers tracked and nonignored untracked files; ignored configuration/dependency contents are not captured. External state still requires observation.

If required proof is blocked, keep the criterion open. Open a PR for review with the precise gap once independent work is complete, following [delivery](delivery.md). Review status does not close verification criteria or authorize merge. Passing a component check is useful progress but cannot close an application criterion. If the generated verifier drifts, repair it and rerun; report actual product regressions separately from verification-documentation corrections.
