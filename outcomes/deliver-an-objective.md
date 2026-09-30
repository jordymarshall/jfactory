# Job to be done: Deliver an objective without babysitting

Serves outcomes 1 and 2 in [README.md](README.md). Feature: `agent-instructions` and `evidence-receipts` in `.jfactory/verification.json`. How to drive it: give an agent an objective in a set-up repository and observe the loop in `skills/jfactory/SKILL.md`.

## Who and why

- **User:** the owner handing an agent a goal.
- **Trigger:** an objective in the task location, or a request in chat.
- **Outcome they want:** a verified PR with evidence, without saying "keep going" or re-checking claims.
- **Not in scope:** deciding product direction the owner hasn't settled.

## Goals and how each is proven

| Goal | How it's proven |
| --- | --- |
| The agent keeps working until the change is right (criteria, job goals, standards and outcomes) or is precisely blocked | Eval "Component fixtures pass, full-app auth unavailable"; eval "User requests continuation after the agreed objective is complete" (model trials) |
| "Done" means right and always carries evidence; stale or failed receipts can't be reused | `tests/test_evidence.py` `test_new_failure_does_not_reuse_old_success`, `test_changed_source_and_task_invalidate_proof` |
| Judgment criteria are scored against a rubric by another model family | `tests/test_evidence.py` `test_judgment_needs_rubric_independent_judge_and_inspected_artifacts` |
| Every PR states its objective, and each criterion names the job goal it serves | `tests/test_verify_plan.py` `test_non_static_pr_must_state_its_objective`; objective template review by the verifier |
| The final message names the actual evidence, PR and commit | Eval "Agent implemented scene audio behavior and is about to say only 'confirmed'" (model trial) |

## Quality rubric

1. The agent asks only consequential questions and keeps working on independent parts while waiting.
2. Gaps are stated prominently, never hidden in a passing summary.

## Evals

| Scenario | Expected result |
| --- | --- |
| The delivery scenarios in `evals/scenarios.md` | As stated there |

## When this document and the product disagree

Update this document in the same PR when the loop changed on purpose; otherwise report the defect.
