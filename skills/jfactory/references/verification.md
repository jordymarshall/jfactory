# Verification contract

Choose evidence from the claim, not from whichever test is easiest to run. Engineering correctness, experience quality, customer value and agent-workflow effectiveness are separate conclusions.

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
