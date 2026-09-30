# Outcomes

The business level: who the product is for, the outcomes that matter and how they are measured. Every job document below serves one of these outcomes, and every work item serves a job. Link the product brief or PRD rather than copying it; keep only what verifiers need to judge whether a change serves the business.

## Customer

REPLACE: who the product is for, their situation and the problem, linking the canonical product brief or PRD section.

## Outcomes and measures

| Outcome | How it is measured | Source |
| --- | --- | --- |
| REPLACE: a result for the customer or the business, for example "a small team launches its first tested ad in a day" | REPLACE: a measure you can read, for example "median time from sign-up to first launch" | REPLACE: PRD section or owner decision |

## Non-goals

REPLACE: what the product deliberately does not do. A change that moves toward a non-goal fails verification unless the owner changed this list.

## Jobs to be done

One document per thing users do, in their words. Each lists standing goals and how each is proven.

| Job | Document | Serves outcome |
| --- | --- | --- |
| REPLACE: for example "Plan a campaign brief" | `outcomes/plan-a-campaign-brief.md` | REPLACE |

## How the levels fit together

- **This file:** why the product exists and what counts as success. Changes rarely, by owner decision.
- **Standards** (`.jfactory/standards.md`): what good looks like across every job (brand, design, accessibility and the rest).
- **Job documents** (`outcomes/<job>.md`): the standing goals of one thing users do, each with how it is proven.
- **Work items** (the objective in the issue or PR): the criteria for one change, each naming the job goal it adds, changes or relies on.

Verifiers check a change against all four: its own criteria, the standing goals of the jobs it touches, the standards, and this file's outcomes and non-goals.
