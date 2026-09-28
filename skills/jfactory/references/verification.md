# Verification contract

Choose evidence from the claim, not from whichever test is easiest to run. Engineering correctness, experience quality, customer value and agent-workflow effectiveness are separate conclusions.

## Objective contract

Before substantial implementation, put the following in the existing task or issue. Keep one canonical acceptance record; link machine-readable tests/criteria to it when useful.

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

These are different claims, not a ladder where one automatically proves all others. A changed signed-in save journey normally needs application evidence with independent storage readback. A real-provider requirement also needs provider evidence. A library/CLI should exercise its actual public interface, not invent a browser requirement. Documentation-only edits can use static checks.

Record expected state before execution, the actual user action/command, observed result and independent side-effect observation. Check reload/readback, access boundaries, retries, idempotency, failure recovery and downstream handoffs where the objective requires them. Screenshots complement assertions; a success toast alone does not prove persistence. Tests may stub isolated external boundaries, but then they cannot prove those external systems worked.

Capture the code revision and dirty source identity, exact command, environment identity without secrets, assertions/results and durable evidence links. Keep failed attempts. Ensure cleanup preserves evidence and only removes owned instances/test data. Negative controls should demonstrate that a broken behavior or failed command cannot be reported as passed. Do not weaken assertions, skip a failing check or edit expected outputs just to obtain green results.

## Change-aware verification and the merge gate

Verification needs follow from what a PR changes, not from a fixed repository-wide check. The repository's `.jfactory/verification.json` links code paths to the project verifier's feature-map entries and to CI suites (see [the example](../templates/verification.example.json)). Setup creates it from the actual layout and verifier; `maintain-verification-skill` audits and any change to a feature's code keeps it current.

1. **Plan.** `python3 <skill>/scripts/verify_plan.py plan --base origin/<base>` lists the affected features with their recipes and the CI suites to run. Changed files that match no feature or static pattern, and any change to `.jfactory/` or `.github/workflows/`, require **full** verification of every feature. Static patterns cover only files that cannot change runtime or agent behavior. Put the plan in the PR, alongside the objective's own acceptance criteria.
2. **Loop.** The implementer runs those recipes and the objective's criteria until they pass on the current head.
3. **Automated floor.** CI runs the suites the plan names; required CI uses one aggregate check that fails if a suite the plan needs was skipped, and treats unknown files as full.
4. **Independent verdict.** A verifier from a different model family (the default is GPT-6 Sol in fast mode) re-runs the plan against the PR preview or staging at the current head and posts the verdict with `verify_plan.py verdict --pr <n> --head <sha> --verdict verified --verifier <agent/model> --implementer <agent/model> --evidence <link> [--full]`. It refuses a stale head, a same-family verifier and incomplete coverage. Static-only changes need no independent verdict.
5. **Required status.** The [`jfactory verified` workflow](../templates/jfactory-verified.yml) re-evaluates on every push and comment, from the base branch's script and mapping, and sets the `jfactory verified` commit status. It passes only for a trusted verdict comment at the current head that covers the plan. A new push resets it. Make it a required check next to CI.

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

The runner uses `.context/jfactory/` for local evidence and excludes only that directory from its source fingerprint. Never put application source there. No credentials in command arguments or environment labels; review logs before sharing. Only evidence IDs, hashes and existing task records need be durable; publish selected sanitized artifacts when a PR reviewer needs them, not all local logs. The code fingerprint covers tracked and nonignored untracked files; ignored configuration/dependency contents are not captured. External state still requires observation.

If required proof is blocked, keep the criterion open. Open a PR for review with the precise gap once independent work is complete, following [delivery](delivery.md). Review status does not close verification criteria or authorize merge. Passing a component check is useful progress but cannot close an application criterion. If the generated verifier drifts, repair it and rerun; report actual product regressions separately from verification-documentation corrections.
