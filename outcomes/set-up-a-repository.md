# Job to be done: Set up or update a repository

Serves outcome 1 in [README.md](README.md). Features: `installer`, `setup-check` and `agent-instructions` in `.jfactory/verification.json`. How to drive it: point an agent at jfactory and say "Setup jfactory" in an existing or empty repository; follow `skills/jfactory/references/setup.md`. The [shared goals and evidence limits](README.md#goals-shared-by-every-job) also apply. Standing goals below are pending owner review.

## Who and why

- **User:** an owner or developer adopting, updating or repairing jfactory in any existing or empty repository.
- **Trigger:** "Setup jfactory", an explicitly requested update, or a setup check showing drift.
- **Outcome they want:** a repository their agents can work in unattended, with gates that make "done" mean right and proven, after answering only product questions.
- **Not in scope:** choosing the product's direction or building a feature during setup.

## Goals and how each is proven

| Goal | How it's proven |
| --- | --- |
| Installation preserves the owner's files and refuses conflicting updates | `tests/test_install.py` (`test_preserves_instructions_and_is_idempotent`, `test_modified_payload_refuses_update_without_mutation`) |
| An authorized update preserves project decisions and reconciles new requirements in the same setup record; normal work does not update the bundle silently | `tests/test_install.py` `test_reviewed_update_removes_old_payload_preserves_surrounding_text` checks installation preservation; model trial "Update an adopted repository with new setup requirements" checks reconciliation and intent |
| Setup continues through adoption without another prompt after install | `evals/scenarios.md` "Setup jfactory" after the installer succeeds (model trial) |
| The agent discovers the real user interface, launch command, existing harness, observable state and isolation limits from the repository, rather than asking the owner to supply technical facts or generating placeholders | Model trial "First setup discovers its own verification harness"; inspect the code-grounded launch/doctor/drive/evidence/cleanup instructions and any precise startup blocker |
| First adoption confirms every product question with the owner, even when the README suggests answers; updates reuse settled answers and ask only about unresolved intent | `tests/test_setup_check.py` `test_interview_must_cover_every_topic`; eval "Setup jfactory" on an obvious README and "Update an adopted repository with new setup requirements" |
| The agent drafts the repository's user-recognizable jobs, feature boundaries, standing goals and standards, confirms unresolved product intent with the owner, and does not treat an old interview as approval of a new map | Model trial "Owner interview exists but the new job map is unreviewed"; inspect the proposed map, the owner's confirmation or corrections, and unresolved decisions in the setup record |
| Readiness is never overstated: unverified areas stay open with their owner step | `tests/test_setup_check.py` `test_product_cannot_be_verified_without_owner_answers`, `test_verified_delivery_needs_enforced_remote_gates` |
| Verifiers get sources of truth: outcomes, a standards map and a document per job, each goal with how it's proven | `tests/test_setup_check.py` `test_standards_map_names_real_sources_and_how_to_prove_them`; `tests/test_verify_plan.py` `test_audit_asks_each_screen_feature_for_a_proven_journey` |
| Before claiming the project verifier is ready, the agent follows its own instructions end to end on one mapped feature: launch, health-check, drive, capture action/result and side effects, then clean up only owned resources and confirm the proof survives | Model trial "A generated verifier must prove itself"; inspect real target identity, the drive, side-effect readback and surviving artifacts after successful and failed attempts. One feature proves the harness, not the whole feature map |
| Each mapped feature has concrete user entry points, driving instructions, expected observable results and prerequisites; requested maintenance checks every mapped feature from source and live use | Model trial "Verification maintenance separates drift from regression"; review coverage and clean/changed/blocked result. A documented prerequisite or an unreachable feature is a limit, not proof it works; maintenance does not silently repair product code or rewrite goals to match defects |
| Setup leaves checks fast and proportional: the owner chooses when the whole suite runs | `tests/test_verify_plan.py` `test_owner_chooses_when_the_whole_suite_runs`, `test_recommendation_follows_the_suite_cost_and_test_data` |

## Quality rubric

1. Every question the owner is asked is a product question or a consequential authorization.
2. The adoption PR names each open area with the exact owner step.
3. Nothing product-specific lands in the bundle.

## Evals

| Scenario | Expected result |
| --- | --- |
| The setup adoption cases in `evals/scenarios.md`, including map confirmation and updating an adopted repository | As stated there; model trials pending |

## When this document and the product disagree

If the document is out of date because setup changed on purpose, update it in the same PR and link the decision. If setup no longer does what this says, report it as a defect; never edit this document to match.
