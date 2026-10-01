# Outcomes

The business level for jfactory itself. The product brief in [AGENTS.md](../AGENTS.md#product-brief) and the owner interview in [the setup record](../.jfactory/setup.md#owner-interview) establish the direction. These documents translate it into standing goals so verifiers can judge whether a change serves it.

## Decision and evidence status

The owner agreed the five job boundaries on 2026-09-30, confirmed the complete contract on 2026-10-01 and delegated finalization of jfactory only. The detailed proof recipes are agent-authored translations of that confirmed contract, not a claim that the owner inspected each row or that the workflow has been proven to meet them. Keep consumer-specific facts in each consumer repository, never in this map or the installed bundle. Behavioral effectiveness remains subject to the separate evaluation objective in the setup record.

## Customer

The owner first, then any developer who points their coding agent at this repository. They want agents to work for hours without being told "keep going", without calling work done that isn't right (unproven, or right only by its own checks), without every PR needing a human review, and without chaos when many run at once.

## Outcomes and measures

In the owner's order:

| Outcome | How it is measured | Source |
| --- | --- | --- |
| Setup plus a first feature reach a verified, merged PR with the owner only answering product questions | Owner interventions per adoption (count of non-product messages the owner had to send) | AGENTS.md success measure 1 |
| Agent PRs merge without owner fixes | Share of agent PRs merged with no owner commit or requested change | AGENTS.md success measure 2 |
| Blinded cross-model evals show it helps | Judge scores for jfactory against a baseline on `evals/scenarios.md` tasks | AGENTS.md success measure 3 |

## Non-goals

- Anything that works for only one repository or product: product facts belong in each project's files, never in the bundle.
- Releasing production on its own.

## Jobs to be done

| Job | Document | Serves outcome |
| --- | --- | --- |
| Set up or update a repository | [set-up-a-repository.md](set-up-a-repository.md) | 1 |
| Deliver an objective without babysitting | [deliver-an-objective.md](deliver-an-objective.md) | 1, 2 |
| Merge verified changes safely | [merge-verified-changes.md](merge-verified-changes.md) | 2 |
| Run many agents in parallel | [run-many-agents.md](run-many-agents.md) | 1, 2 |
| Research an experience to inform product decisions | [research-an-experience.md](research-an-experience.md) | 1, 2 |

Experience review of a change to the owner's product belongs to delivering an objective. Standalone reference research has its own job because its deliverable is findings for a decision, not an implemented feature. Owner-requested production release remains supporting guidance, not an additional core job; autonomous production release remains out of scope.

## Goals shared by every job

| Goal | How it's proven |
| --- | --- |
| The workflow works in any repository; project facts and settled owner decisions stay in that project's own records | Verifier review of installation and adoption diffs; model trial "Job map applies to unrelated repositories" in `evals/scenarios.md` |
| Corrections are classified as one-off feedback or recurring/systemic failures; recurring failures get a durable fix at the strongest suitable layer instead of another reminder | Model trials "Owner correction should stick across jobs" and "One-off feedback is not a standing rule" in `evals/scenarios.md`; inspect the fix and its failing-before, passing-after reproduction. Instruction-only fixes need separate model trials, not a claim that a unit test proves the agent learned |
| Product intent is owner-confirmed; assumptions, missing access and missing proof remain visible, without stopping independent work | Verifier review of the objective, setup record or research handoff; model trials for incomplete setup, blocked application evidence and reference research |
| Proof observes the real output and relevant side effects through the user's interface, with concrete expected results; self-reports, copied constants and a green build are not substitutes | Verifier review of reproducible commands and artifacts; model trial "Checks are green but the observable result is wrong" in `evals/scenarios.md`; include a negative control that demonstrates the check detects the claimed defect |
| Execution reuses existing tools and canonical records, makes the smallest justified change and does not ask the owner questions the repository or an experiment can answer | Model trial "First setup discovers its own verification harness"; verifier review of changed code and records against the agreed objective. Necessary product decisions and consequential authorizations still belong to the owner |
| Work reaches its verified result promptly, reducing avoidable waiting, repeated work and slow feedback without weakening criteria, required review or safety | Model trial "Faster delivery preserves the proof contract" in `evals/scenarios.md`; compare equivalent tasks with the same acceptance criteria and evidence scopes, record elapsed time and its breakdown, and report result quality alongside timing. Missing proof is not a speed win |
| Resources are proportionate to the task and any agreed budget, with usage measured per verified outcome rather than saved by weakening the model, review or evidence policy | Model trial "Resource efficiency is not a cheaper unverified result"; inspect recorded usage, total compute and outcomes under comparable conditions. Distinguish resource use from wall-clock waiting; report unavailable cost data as unknown, never zero |
| At meaningful checkpoints, canonical records and the handoff state what is done, running, blocked or waiting, with the actual evidence, next action and any exact owner step | Model trial "Progress and recovery do not need owner reconstruction"; compare status with real tool results and source revisions, then have a replacement session resume from the recorded next action. Do not substitute guessed progress percentages or repeated liveness messages for state |

Learning from corrections is a goal across the five jobs, not a sixth job. A local fix belongs in the consumer repository; a portable improvement belongs in jfactory through its own objective and PR. Neither authorizes unrelated work or inventing a new product requirement.

## Speed and its measurement

Speed applies across the five jobs, not as another job or a replacement for "done means right". Measure time from the request to its verified result: completed adoption, delivered research or a verified PR, including merge when merge is in scope. Record when scope and criteria were agreed, and separate active work, verification/review/CI waiting, rework and necessary owner-decision/access waiting so a bottleneck can be diagnosed instead of hidden. Report failed and blocked attempts with their outcomes, not only successful timings.

Compare equivalent tasks and disclose the workload, revision, tools/models, environment and sample count. Wall-clock time is not compute cost: parallel work can finish sooner while consuming more resources. Product response time and the agent workflow's delivery time are separate measures; neither proves the other improved. Reuse canonical objectives and existing run artifacts rather than requiring another permanent report for every task.

Targets and budgets belong in the repository's own standards or objective, based on measured baselines and owner priorities. There is no universal deadline for every repository, and no speed improvement has been demonstrated by adding these goals. Use change-aware checks, existing harnesses and safe independent parallel work to shorten feedback; retain all required criteria, evidence scopes, review and the owner's whole-suite policy.

## Resource efficiency and predictable progress

Measure available model usage, tokens, CI compute or reported cost against the verified result and the attempts needed to reach it. Disclose failures and rework, not only the cheapest successful attempt. Keep the task's model tier, independent review and required evidence; avoid duplicate agents, redundant whole-suite runs and unnecessary tooling within those requirements. Project budgets belong in that project's standards or objective; this contract neither invents a universal spending cap nor grants new spend authorization.

Keep state in the existing objective, setup record or research handoff, as appropriate. A reader should see the result reached, evidence revision, current blocker and next action without reconstructing the chat. Record meaningful transitions rather than producing another status document or constant chatter. A paused or ended agent session does not imply background supervision: report that limit rather than promising updates no host mechanism supplies.

## Method sources and adaptations

These goals draw on Lauren Tan's original pstack methods, pinned at version 0.15.5; [the upstream record](../skills/jfactory/vendor/pstack/UPSTREAM.md) identifies the commit and attribution. Skills and principles inform how the five jobs work; they are not additional jobs or proof that jfactory already meets the goals.

| Method | How it informs the contract |
| --- | --- |
| [Create verification](../skills/jfactory/vendor/pstack/skills/create-verification-skill/SKILL.md) and [maintain verification](../skills/jfactory/vendor/pstack/skills/maintain-verification-skill/SKILL.md) | Setup discovers technical facts from the repo, proves its generated verifier once through a real feature, and maintains source and live coverage without hiding regressions as doc drift |
| [Prove it works](../skills/jfactory/vendor/pstack/skills/principle-prove-it-works/SKILL.md) and [test behavior](../skills/jfactory/vendor/pstack/skills/principle-test-behavior-not-implementation/SKILL.md) | Check actual results and side effects, with assertions that can fail for the defect; table-consistency checks remain useful but are not workflow proof |
| [Encode lessons in structure](../skills/jfactory/vendor/pstack/skills/principle-encode-lessons-in-structure/SKILL.md) and [fix root causes](../skills/jfactory/vendor/pstack/skills/principle-fix-root-causes/SKILL.md) | Distinguish one-off feedback from patterns; recurring fixes belong in mechanisms, with no redundant reminder when the mechanism enforces the rule |
| [Sequence verifiable units](../skills/jfactory/vendor/pstack/skills/principle-sequence-verifiable-units/SKILL.md), [autonomous run](../skills/jfactory/vendor/pstack/skills/poteto-mode/playbooks/autonomous-run.md) and [session pickup](../skills/jfactory/vendor/pstack/skills/poteto-mode/playbooks/session-pickup.md) | Use checkable milestones, retain supported improvements and recover from a concise trail while verifying inherited claims on the actual artifact |
| [How](../skills/jfactory/vendor/pstack/skills/how/SKILL.md), [why](../skills/jfactory/vendor/pstack/skills/why/SKILL.md) and [architect](../skills/jfactory/vendor/pstack/skills/architect/SKILL.md) | Ground consequential changes in actual runtime flow and existing decisions; compare viable designs before committing to a shape, without making every small fix a multi-model design exercise |
| [Separate shared state](../skills/jfactory/vendor/pstack/skills/principle-separate-before-serializing-shared-state/SKILL.md) | Give workers independent write targets; use enforced single ownership or serialization only where sharing is necessary |
| [Laziness protocol](../skills/jfactory/vendor/pstack/skills/principle-laziness-protocol/SKILL.md) and [never block on the human](../skills/jfactory/vendor/pstack/skills/principle-never-block-on-the-human/SKILL.md) | Reuse, simplify and execute reversible work; reserve owner questions for product intent and consequential authorization |
| [Eval playbook](../skills/jfactory/vendor/pstack/skills/poteto-mode/playbooks/eval.md) | Judge equivalent isolated attempts blind, inspect actual actions and outputs, and do not expose evaluator notes or rubrics to candidates |

jfactory retains its own boundaries: owner-confirmed product intent, scoped objectives, host-compatible tools, the repository's branch-update policy and protected delivery. Upstream defaults do not authorize production release, unrelated repairs or additional agents. These are jfactory adaptations, not claims about Lauren's guarantees.

## Evaluation and evidence limits

Success measure 3 evaluates how well these jobs work, rather than defining another user job. Run equivalent isolated tasks with blinded variant labels and an independent model-family judge following [the behavioral evaluation cases](../evals/scenarios.md). Candidate-visible prompts, paths and files must not reveal evaluator notes, rubrics, model identities or that another candidate exists; evaluator-only cases are not candidate prompts. Report artifacts, owner interventions, corrections and time/cost where measurable, not judge scores alone.

Each job names executable controls and the behavioral trials it needs. Passing a control proves only the behavior that control exercises; fake GitHub/Conductor tests and disposable browser pages do not prove live adoption, coordination or customer usability. Model trials remain pending until a report records the candidate revision, actual artifacts and outcomes. Confirming this contract creates no new proof or readiness claim.

## How the levels fit together

- **This file:** why jfactory exists and what counts as success. Changes by owner decision.
- **Standards** ([.jfactory/standards.md](../.jfactory/standards.md)): what good looks like everywhere.
- **Job documents** (this folder): the standing goals of one thing users do, each with how it is proven.
- **Work items** (the objective in a `jfactory-objective` issue or the PR): the criteria for one change, each naming the job goal it adds, changes or relies on.
