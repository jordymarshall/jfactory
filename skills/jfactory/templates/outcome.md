# Job to be done: REPLACE with what the user does, in their words (for example "Plan a campaign brief")

Lives at `outcomes/<job>.md`. Serves: REPLACE with the business outcome in `outcomes/README.md` it moves. Feature: `REPLACE` in `.jfactory/verification.json`, which names this file as its `"outcome"`. How to drive it: REPLACE with the verification skill's feature recipe, if there is one.

These goals are standing: they hold for every change, not just one piece of work. A work item's objective names the goals here it adds, changes or relies on. Verifiers read this document for every change to the feature, check the change against it, and cite it with `verify_plan.py verdict --standards <this file>`.

## Who and why

- **User:** REPLACE: who does this, and their situation.
- **Trigger:** REPLACE: what makes them start.
- **Outcome they want:** REPLACE: the result they care about, not a feature description.
- **Not in scope:** REPLACE: what this journey deliberately does not do.

## Goals and how each is proven

Every row says how it is proven: a test or command that runs in CI, a judgment rubric the verifier scores, reviewed screenshots, or a measure read from production. `audit` warns about any row without one.

| Goal or acceptance criterion | How it's proven |
| --- | --- |
| REPLACE: an observable result, for example "a saved brief survives reload with its exact words" | REPLACE: for example the goal test `e2e/goals/plan-a-brief.spec.ts` "a saved brief survives reload" ([goal tests](../references/goal-tests.md)), or `e2e/brief-editor.spec.ts` "storyboard edits ... survive reload" |
| REPLACE: a quality, for example "the empty state explains what to do next" | REPLACE: for example "judgment rubric below, desktop and mobile screenshots" |
| REPLACE: a measure, for example "first page of briefs renders in under 2s with 1,000 briefs" | REPLACE: for example `e2e/briefs-scale.spec.ts` timing assertion |

## Quality rubric

Scored by a verifier from another model family on reviewed screenshots or a walkthrough, pass or fail per point:

1. REPLACE: for example "every label and message passes the project's writing rules (standards map: Brand, voice and copy)".
2. REPLACE

## Evals

Scenarios a verifier or model trial runs end to end, with the expected result:

| Scenario | Expected result |
| --- | --- |
| REPLACE | REPLACE |

## When this document and the product disagree

Decide which one is wrong. If the document is out of date because the product changed on purpose, update it in the same PR and link the decision. If the product no longer does what this says, the change fails verification: report it as a defect or an objective. Never edit this document to match broken behaviour.
