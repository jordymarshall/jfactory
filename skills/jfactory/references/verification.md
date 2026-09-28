# Verification contract

Choose evidence from the claim, not from whichever test is easiest to run. Engineering correctness, experience quality, customer value and agent-workflow effectiveness are separate conclusions.

## Objective contract

Write the objective before substantial implementation, in the task location named in the setup record (usually the GitHub issue for the work; for a small fix, the PR description). [templates/objective.md](../templates/objective.md) has the fields. Keep one canonical acceptance record and update it as work progresses; link machine-readable tests/criteria to it when useful. It contains:

- Customer and experience outcome, with owner decisions, agent assumptions and unsettled questions distinguished.
- Scope and non-goals, including constraints and dependencies on other PRs.
- Observable criteria. For each, give the starting state, user action, expected result, independent side-effect/readback check, required scopes and the command or manual observation that can prove it. A missing test is work to implement, not a reason to remove the criterion.
- Execution target, account/data ownership, permitted side effects and any cost/time limits. Note access still needed.
- Review/checkpoint and stop conditions. Carry forward the agreed merge/release policy; identify choices that still need owner judgment.
- Current criterion results, evidence links/revision, unresolved blockers and next action for a resumed session.

For example, "make saving good" is incomplete. "A signed-in customer saves an item, sees it after reload and in a new session, and receives a recoverable error if saving fails" identifies observable behavior. The tests must exercise the real application's auth/storage boundary for that claim. An additional customer interview may still be needed to determine whether saving solves the right problem.

Work through unresolved criteria autonomously. Use failed checks and observations to choose the next correction. Keep the original acceptance standard visible when a proposal changes it; an agent cannot mark a requirement done by deleting its failing assertion. Stop dependent work for a material unresolved decision, inaccessible required service or exhausted agreed budget; continue feasible independent work. Once criteria and required reviews pass, deliver under the recorded PR policy and stop at the agreed boundary.

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

Record expected state before execution, the actual user action/command, observed result and independent side-effect observation. Check reload/readback, access boundaries, retries, idempotency, failure recovery and downstream handoffs where the objective requires them. Screenshots complement assertions; a success toast alone does not prove persistence. Tests may stub isolated external boundaries, but then they cannot prove those external systems worked.

Capture the code revision and dirty source identity, exact command, environment identity without secrets, assertions/results and durable evidence links. Keep failed attempts. Ensure cleanup preserves evidence and only removes owned instances/test data. Negative controls should demonstrate that a broken behavior or failed command cannot be reported as passed. Do not weaken assertions, skip a failing check or edit expected outputs just to obtain green results.

## Change-aware verification and the merge gate

Verification needs follow from what a PR changes, not from a fixed repository-wide check. The repository's `.jfactory/verification.json` links code paths to the project verifier's feature-map entries and to CI suites (see [the example](../templates/verification.example.json)). Setup creates it from the actual layout and verifier; `maintain-verification-skill` audits and any change to a feature's code keeps it current.

1. **Plan.** `python3 <skill>/scripts/verify_plan.py plan --base origin/<base>` lists the affected features with their recipes and the CI suites to run. Changed files that match no feature or static pattern, and any change to `.jfactory/`, `.github/workflows/` or `.github/rulesets/`, require **full** verification of every feature. Static patterns cover only files that cannot change runtime or agent behavior: never agent instructions, skills or verification recipes, which are Markdown too. Put the plan in the PR, alongside the objective's own acceptance criteria.
2. **Loop.** The implementer runs those recipes and the objective's criteria until they pass on the current head.
3. **Automated floor.** CI runs the suites the plan names; required CI uses one aggregate check that fails if a suite the plan needs was skipped, and treats unknown files as full. jfactory does not ship this job: setup builds it on the repository's CI, typically a first job that runs `verify_plan.py plan --base origin/<base> --json` and an aggregate job that checks each named suite succeeded. A repository whose required job always runs every suite already meets the floor.
4. **Risk level.** Each feature in the mapping has a `verify` level, agreed with the owner at setup.
   - **`independent`** (the default) needs the verdict in step 5.
   - **`ci`** needs only the passing CI suites. Use it only for changes that cannot alter what users see or do, what is stored, who can access what, money, or how the rules are enforced: internal refactors covered by tests, test helpers, low-risk tooling, the model-usage reader.

   Anything that changes behavior users see (product and UX), data and storage, sign-in and permissions, payments, migrations, security, agent instructions and the enforcement scripts stays `independent`. A PR touching both levels needs the stricter one, and its verdict must cover the `independent` features. Unmapped files and gate files (`.jfactory/`, workflows, rulesets) always need a full verdict. That is also how a change that lowers a level gets verified: the level is read from the base branch, so a PR cannot lower its own. When unsure, choose `independent`.
5. **Independent verdict.** A verifier from a different model family (the default is GPT Luna 6 in fast mode) re-runs the plan against the PR preview or staging at the current head, scores each `judgment` criterion against its rubric, lists every criterion's result in the verdict's evidence, and posts the verdict with `verify_plan.py verdict --pr <n> --head <sha> --verdict verified --verifier <agent/model> --implementer <agent/model> --evidence <link> [--full]`. It refuses a stale head, incomplete coverage, an identity whose model family it cannot tell, and a same-family verifier unless the mapping records the owner's `"allow_same_family": true`. Static-only changes need no independent verdict.
6. **Required status.** The [`jfactory verified` workflow](../templates/jfactory-verified.yml) re-evaluates on every push and comment. It uses `pull_request_target` and `issue_comment`, so GitHub loads the workflow from the base or default branch rather than the PR; it checks out only the base branch's script and mapping and never runs PR code. It sets the `jfactory verified` commit status. Any change that isn't static fails until the PR description starts with its objective: the first non-empty line is an `## Objective` heading or an `Objective:` line, followed by the objective or a link to its issue (the check confirms presence and minimal length, not quality); set `"require_objective": false` in the mapping to opt out. Otherwise, it passes on its own when the plan is static or CI-only (every affected feature is `verify: ci`). Otherwise it passes only for a trusted verdict comment at the current head that covers the plan's independent features, or every feature when full verification applies. A new push resets it. Make it a required check next to CI.

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
