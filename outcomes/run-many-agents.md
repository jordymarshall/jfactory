# Job to be done: Run many agents in parallel

Serves outcomes 1 and 2 in [README.md](README.md). Feature: `coordination` (`coord.py`) and `model-selection` in `.jfactory/verification.json`. How to drive it: `skills/jfactory/references/coordination.md`.

## Who and why

- **User:** the owner running several objectives at once.
- **Trigger:** work that splits into independent units.
- **Outcome they want:** units run in parallel on suitable models, report reliably, get verified and merge in order, without the owner tracking them.
- **Not in scope:** more concurrent units than the owner's limit.

## Goals and how each is proven

| Goal | How it's proven |
| --- | --- |
| Launches follow the policy and tell workers how to report | `tests/test_coord.py` `test_launch_uses_policy_and_tells_worker_how_to_report` |
| A merge needs a verified verdict at the unit's current head | `tests/test_coord.py` `test_worker_report_sync_verdict_and_merge_gate_on_current_head` |
| Workers' questions block merge until resolved | `tests/test_coord.py` `test_worker_question_becomes_gate_that_blocks_merge_until_resolved` |
| Reviews use another model family and retries are capped | `tests/test_coord.py` `test_review_needs_other_family_and_retries_are_capped` |
| Finished workspaces are archived and sections tidied | `tests/test_coord.py` `test_sync_archives_finished_workspaces_once_their_sessions_stop`, `test_tidy_deletes_only_finished_program_sections` |
| Models are chosen by tier and remaining usage | `tests/test_usage.py` |

## Quality rubric

1. The program issue tells the owner, at a glance, what is running, blocked or waiting on them.

## Evals

| Scenario | Expected result |
| --- | --- |
| The coordination scenarios in `evals/scenarios.md` | As stated there |

## When this document and the product disagree

Update this document in the same PR when coordination changed on purpose; otherwise report the defect.
