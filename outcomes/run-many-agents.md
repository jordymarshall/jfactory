# Job to be done: Run many agents in parallel

Serves outcomes 1 and 2 in [README.md](README.md). Feature: `coordination` (`coord.py`) and `model-selection` in `.jfactory/verification.json`. How to drive it: `skills/jfactory/references/coordination.md`.

The [shared goals and evidence limits](README.md#goals-shared-by-every-job) also apply; the contract is confirmed, not its behavioral effectiveness.

## Who and why

- **User:** the owner running several objectives at once.
- **Trigger:** work that splits into independent units.
- **Outcome they want:** units run in parallel on suitable models, report reliably, get verified and merge in order, without the owner tracking them.
- **Not in scope:** more concurrent units than the owner's limit.

## Goals and how each is proven

| Goal | How it's proven |
| --- | --- |
| Launches follow the policy and tell workers how to report | `tests/test_coord.py` `test_launch_uses_policy_and_tells_worker_how_to_report` |
| Parallel work starts only for agreed independent units, within the owner's limit and dependency order; one small fix does not create a speculative program | `tests/test_coord.py` `test_refuses_incomplete_brief_limit_dependency_hold_and_unknown_model`; model trial "A single small fix is requested in parallel" |
| Workers own separate branches, reports, browser/data state and processes; genuinely shared mutable state has enforced ownership or serialization, not only instructions to be careful | `tests/test_coord.py` `test_worker_report_sync_verdict_and_merge_gate_on_current_head` and `test_stale_report_does_not_override_coordinator_and_close_requires_terminal_units` check report reconciliation; model trial "Parallel workers publish independent results" checks simultaneous reporting and resource isolation |
| A merge follows the risk policy at the unit's current head: an independent verdict when required, or enforced CI for entirely low-risk work; a failed verdict always blocks | `tests/test_coord.py` `test_worker_report_sync_verdict_and_merge_gate_on_current_head`, `test_low_risk_unit_merges_on_ci_without_a_verdict`, `test_a_failed_verdict_blocks_even_a_low_risk_merge` |
| Workers' questions block merge until resolved | `tests/test_coord.py` `test_worker_question_becomes_gate_that_blocks_merge_until_resolved` |
| Reviews use another model family and retries are capped | `tests/test_coord.py` `test_review_needs_other_family_and_retries_are_capped` |
| Finished workspaces are archived and sections tidied | `tests/test_coord.py` `test_sync_archives_finished_workspaces_once_their_sessions_stop`, `test_tidy_deletes_only_finished_program_sections` |
| Workspaces launched for a PR archive themselves once it merges or closes, without touching the owner's | `tests/test_coord.py` `test_launch_names_a_pr_workspace_by_convention`, `test_tidy_archives_only_idle_convention_workspaces_whose_pr_finished`, `test_sync_verdict_merge_and_close_archive_finished_pr_workspaces`, `test_missing_or_failing_conductor_never_fails_verdict_sync_or_merge`, `test_workspace_tidy_is_time_boxed`, and the negative controls `test_a_working_session_on_a_later_page_keeps_the_workspace`, `test_repository_identity_is_exact_host_owner_and_name`, `test_only_an_idle_session_status_lets_a_workspace_go`, `test_names_must_match_the_convention_exactly`, `test_a_slow_conductor_cannot_hold_up_a_verdict`, `test_a_github_failure_is_reported_once_not_per_workspace` |
| A verdict that blames a rule becomes an owner decision the unit waits on, not a fix task; one that blames the change becomes a fix task | `tests/test_coord.py` `test_sync_turns_a_rules_verdict_into_an_owner_decision_not_a_fix_task`, `test_sync_turns_a_change_verdict_into_a_fix_task`, `test_verdict_command_routes_a_rules_failure_to_the_owner` |
| Models are chosen by tier and remaining usage | `tests/test_usage.py` |
| The owner can pause and resume a program; workers stop safely and preserve work, and new launches remain held until resumed | `tests/test_coord.py` `test_refuses_incomplete_brief_limit_dependency_hold_and_unknown_model` checks launch holds; model trial "A worker is told the program is on hold mid-task" checks worker behavior and resumption |
| A replacement coordinator recovers from the program issue and actual workspace state without relaunching completed units or modifying unrelated workspaces | Model trial "Coordinator session ends mid-program"; `tests/test_coord.py` `test_tidy_deletes_only_finished_program_sections` checks cleanup ownership, not full recovery |
| Shared-contract and dependent units integrate current main and refresh affected verification after every overlapping merge | Model trial "Overlapping units must integrate and reverify"; inspect merge order, integrated revisions and new evidence, not only isolated unit verdicts |

## Quality rubric

1. The program issue tells the owner, at a glance, what is running, blocked or waiting on them.

## Evals

| Scenario | Expected result |
| --- | --- |
| The coordination scenarios in `evals/scenarios.md` | As stated there |

## When this document and the product disagree

Update this document in the same PR when coordination changed on purpose; otherwise report the defect.
