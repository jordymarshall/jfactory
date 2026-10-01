# Job to be done: Merge verified changes safely

Serves outcome 2 in [README.md](README.md). Feature: `coordination` (`verify_plan.py`, the gate workflow and templates) in `.jfactory/verification.json`.

## Who and why

- **User:** the owner, who no longer reviews every PR by hand.
- **Trigger:** an agent's PR is ready.
- **Outcome they want:** only changes that are right can merge: proven at their exact commit, by an independent reviewer, against their criteria, their jobs' goals, the standards and the outcomes. Passing checks alone never merges.
- **Not in scope:** releasing production.

## Goals and how each is proven

| Goal | How it's proven |
| --- | --- |
| A verdict counts only at the current head, from another model family, with CI green | `tests/test_verify_plan.py` `test_status_follows_verdict_at_current_head`, `test_verdict_refuses_stale_head_same_family_and_missing_coverage`, `test_recorded_owner_decision_allows_same_family` |
| Screen changes need a step-by-step walkthrough, with a screenshot and a note after every action | `tests/test_study.py` `test_every_step_captures_what_the_user_now_sees`; `tests/test_verify_plan.py` `test_screen_changes_need_reviewed_screenshots` |
| Screen changes need screenshots a vision-capable model reviewed | `tests/test_verify_plan.py` `test_screen_changes_need_reviewed_screenshots` |
| Verdicts name the standards and job documents they checked | `tests/test_verify_plan.py` `test_verdicts_name_the_standards_and_journeys_they_checked` |
| Tests, agent instructions, screens and source-of-truth documents always get the independent verifier | `tests/test_verify_plan.py` `test_tests_instructions_and_screens_always_need_the_verifier`, `test_standards_and_journey_documents_are_always_reviewed` |
| A PR cannot edit its own gate | `tests/test_verify_plan.py` `test_gate_files_always_need_full_verification`; the workflow runs from the base branch (`skills/jfactory/templates/jfactory-verified.yml`) |
| A PR names the outcomes/ documents it serves and why it's right | `tests/test_verify_plan.py` `test_verdicts_name_the_standards_and_journeys_they_checked` |
| Every failed or blocked verdict says whether the change or a rule is wrong; a wrong rule still blocks the merge, reaches the owner once per PR with a proposed adjustment, and is never waived by an agent | `tests/test_verify_plan.py` `test_failed_and_blocked_verdicts_name_their_cause`, `test_a_rules_verdict_asks_the_owner_once_per_pr_and_still_blocks`, `test_a_fix_after_a_rules_verdict_also_links_the_decision`, `test_old_verdicts_without_a_cause_still_evaluate` |
| Merged PRs that fell short are noticed, not assumed fine, and rules flagged on more than one PR surface | `tests/test_method_audit.py`; the weekly `jfactory method audit` workflow |
| GitHub enforces both checks with no bypass | `tests/test_setup_check.py` `test_ruleset_template_requires_both_checks_without_bypass` |

## Quality rubric

1. A reviewer reading the verdict comment can see what was checked, against what, and where the evidence is.

## Evals

| Scenario | Expected result |
| --- | --- |
| The verification and auto-merge scenarios in `evals/scenarios.md` | As stated there |

## When this document and the product disagree

Update this document in the same PR when the gate changed on purpose; otherwise report the defect.
