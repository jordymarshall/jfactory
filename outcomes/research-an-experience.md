# Job to be done: Research an experience to inform product decisions

Serves outcomes 1 and 2 in [README.md](README.md): research helps the owner settle product questions before agents implement them. Features: `agent-instructions` and `ux-helpers` in `.jfactory/verification.json`. How to drive it: ask an agent to study an approved reference experience using `skills/jfactory/skills/jfactory-ux/SKILL.md`.

The [shared goals and evidence limits](README.md#goals-shared-by-every-job) also apply. Standing goals below are pending owner review.

## Who and why

- **User:** an owner or developer deciding how a customer's task should work.
- **Trigger:** a request to study another app or an open experience question that needs reference research.
- **Outcome they want:** an evidence-backed walkthrough that makes useful patterns and tradeoffs clear, without having to drive and document the study themselves.
- **Not in scope:** implementing recommendations without agreement, copying another product's customer assumptions, claiming customer usability from an agent critique, or using unapproved accounts and destructive actions.

## Goals and how each is proven

| Goal | How it's proven |
| --- | --- |
| The study has a bounded question, agreed access and relevant journeys; the agent investigates the real experience rather than inventing observations | Model trial "Standalone reference research has a bounded question"; inspect the research objective, actual browser actions and evidence against `skills/jfactory/skills/jfactory-ux/SKILL.md` |
| The owner can provide authenticated access through the supported handoff without exposing credentials or unrelated sessions | `tests/test_study.py` `test_rejects_path_traversal_and_credentials`, `test_refuses_global_cleanup_or_session_takeover`, `test_review_server_serves_evidence_but_not_profile_or_traversal`; `tests/dashboard_smoke.py` checks a disposable sign-in handoff, not real third-party authentication |
| Relevant journeys, interactions and states are covered with inspected screenshots or video; missing access or evidence is reported as a limit, not a complete study | `tests/test_study.py` `test_rejects_missing_external_and_active_evidence`, `test_incomplete_research_cannot_render_as_complete`; `tests/browser_smoke.py` checks browser mechanics; model trial "Reference research is blocked on one journey" checks honest coverage |
| The agent health-checks each owned browser instance before driving and after surprising failures; it resets or relaunches only what it owns, cleans up failed attempts and retains captured proof | Model trial "Failed drives preserve proof and clean owned resources"; inspect process/session ownership, recovery actions and surviving artifacts after teardown. Browser helper smokes are not proof that an agent follows this recovery protocol |
| The walkthrough separates observations, inferences and recommendations, with artifact links and rationale for the owner's product question | `tests/test_study.py` `test_renders_escaped_text_and_real_artifact_link` checks report rendering; model trial "Standalone reference research has a bounded question" requires an independent judge to inspect the walkthrough and source artifacts |
| Recommendations remain proposals until the owner agrees; the handoff names open decisions and does not start implementation or claim customer validation | Model trial "Reference findings are not product requirements"; inspect the handoff, owner decisions and subsequent actions |

## Quality rubric

1. Each consequential observation points to evidence the reviewer can inspect.
2. The owner can tell what was observed, what was inferred, what was not reached and what is proposed.
3. Recommendations address the agreed question and explain tradeoffs, rather than copying another app's behavior as a requirement.
4. The agent asks only for consequential product decisions or necessary access, and continues independent research when one journey is blocked.

## Evals

| Scenario | Expected result |
| --- | --- |
| The reference research cases in `evals/scenarios.md` | As stated there; model trials pending |

## When this document and the product disagree

If research changed on purpose, update this document in the same PR and link the decision. If the workflow invents findings, hides gaps or implements unapproved recommendations, report the defect; do not weaken the goals to match it.
