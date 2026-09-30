# Job to be done: Set up a repository

Serves outcome 1 in [README.md](README.md). Feature: `setup-check` in `.jfactory/verification.json`. How to drive it: install into a disposable repository with `scripts/install.py`, then follow `skills/jfactory/references/setup.md`.

## Who and why

- **User:** an owner or developer adopting jfactory in an existing or empty repository.
- **Trigger:** "Setup jfactory".
- **Outcome they want:** a repository their agents can work in unattended, with gates that make "done" mean right and proven, after answering only product questions.
- **Not in scope:** choosing the product's direction or building a feature during setup.

## Goals and how each is proven

| Goal | How it's proven |
| --- | --- |
| Installation preserves the owner's files and refuses conflicting updates | `tests/test_install.py` (`test_preserves_instructions_and_is_idempotent`, `test_modified_payload_refuses_update_without_mutation`) |
| Setup continues through adoption without another prompt after install | `evals/scenarios.md` "Setup jfactory" after the installer succeeds (model trial) |
| The owner is asked every product question, even when the README makes it obvious | `tests/test_setup_check.py` `test_interview_must_cover_every_topic`; eval "Setup jfactory" on an obvious README |
| Readiness is never overstated: unverified areas stay open with their owner step | `tests/test_setup_check.py` `test_product_cannot_be_verified_without_owner_answers`, `test_verified_delivery_needs_enforced_remote_gates` |
| Verifiers get sources of truth: outcomes, a standards map and a document per job, each goal with how it's proven | `tests/test_setup_check.py` `test_standards_map_names_real_sources_and_how_to_prove_them`; `tests/test_verify_plan.py` `test_audit_asks_each_screen_feature_for_a_proven_journey` |
| Setup leaves checks fast and proportional: the owner chooses when the whole suite runs | `tests/test_verify_plan.py` `test_owner_chooses_when_the_whole_suite_runs`, `test_recommendation_follows_the_suite_cost_and_test_data` |

## Quality rubric

1. Every question the owner is asked is a product question or a consequential authorization.
2. The adoption PR names each open area with the exact owner step.
3. Nothing product-specific lands in the bundle.

## Evals

| Scenario | Expected result |
| --- | --- |
| The scenarios under "Setup" in `evals/scenarios.md` | As stated there |

## When this document and the product disagree

If the document is out of date because setup changed on purpose, update it in the same PR and link the decision. If setup no longer does what this says, report it as a defect; never edit this document to match.
