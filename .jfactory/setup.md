# jfactory setup record

This repository is jfactory's own source. It uses the bundle in place through [AGENTS.md](../AGENTS.md) instead of an installed copy, so there is no installation receipt; the loaded version is the checked-out commit. Re-running setup updates this record rather than adding another. `skills/jfactory/scripts/setup_check.py --remote` checks it.

## Readiness

Initial readiness reviewed 2026-09-28 against `main` at `6ae1299`. Contract reconciliation on 2026-10-01 incorporates `main` at `2e4ddb9`; current-revision delivery evidence is recorded in [objective #39](https://github.com/jordymarshall/jfactory/issues/39).

| Area | State | Evidence or reason |
| --- | --- | --- |
| Documentation | verified | `AGENTS.md` has the four entry sections, and `tests/test_links.py` passes. The README explains the components, loop routing, objectives, verification, auto-merge, coordination and the correction ladder. Its six diagrams are PNG images rendered from `docs/diagrams/*.mmd`, so they show in GitHub's mobile app; a test keeps them in sync with their sources. |
| Product direction | verified | The owner answered every interview question below on 2026-09-28. The brief in `AGENTS.md` follows those answers. |
| Workspace tools | verified | Python 3 only; the browser smokes also need Node, Chrome and Playwright's ffmpeg. In the Conductor cloud workspace (Python 3.9.25, Node 24.14.1), the unit tests, `check-upstream.py`, `tests/browser_smoke.py` and `tests/dashboard_smoke.py` passed. CI runs Python 3.10. No cloud setup script is needed. |
| Verification | verified | `.jfactory/verification.json` maps every tracked file except the gate paths, which always need full verification. `setup_check.py` confirms it and the `jfactory verified` workflow. This is structural readiness, not proof of agent behavior; the owner confirmed the contract as recorded in the job-map review below. |
| Environments | not applicable | Nothing deploys. The external `loopcraft-status` Vercel project had been linked to this repository by accident (a CLI deploy from inside a checkout), so main merges and branches produced Vercel deployments. That Git link was removed on 2026-10-01 (`DELETE /v9/projects/loopcraft-status/link`; the project's `link` now reads none), and the status page is deployed by hand from outside any checkout. |
| PR delivery | verified | Repository auto-merge is on. The active ruleset "Verified squash merges to main" (id 24086594) requires PRs, squash merges, no bypass, and both `checks` and `jfactory verified` against the latest main. The owner added `jfactory verified` on 2026-09-28, and `setup_check.py --remote` confirmed it. `merge_deploys` is `none`. |

## Owner interview

| Question | Owner answer | Date |
| --- | --- | --- |
| Who is this for, and who struggles today? | The owner first, then the public: any developer who points their coding agent at this repository. | 2026-09-28 |
| What do they do today instead, and what is painful about it? | Babysitting agents with "keep going" (primary pain); agents claiming done without real evidence; reviewing every PR by hand; running many agents in parallel. | 2026-09-28 |
| What outcome would they notice, and how would we know it improved? | All of these, in order: setup plus a first feature reach a verified, merged PR with the owner only answering product questions; agent PRs merge without owner fixes; blinded cross-model evals show jfactory improves results. | 2026-09-28 |
| What is out of scope? | Anything that only works for one specific repository or product. jfactory must apply to any repository and bring engineering best practices to it. Routines and scheduled automation are acceptable where they help. | 2026-09-28 |
| What is the next bounded objective? | Run blinded cross-model evals ([#22](https://github.com/jordymarshall/jfactory/issues/22)). | 2026-09-28 |

## Open owner decisions

None required to finalize the five-job contract. The owner confirmed it on 2026-10-01 and delegated completion of jfactory only; numeric targets remain repository/objective-owned. The external `loopcraft-status` Production deployments that surfaced during remote verification came from an accidental Git link, removed on 2026-10-01, so merges deploy nothing and auto-merge is allowed. Requiring `jfactory verified` on main was applied by the owner on 2026-09-28.

## Job-map review

On 2026-09-30 the owner agreed to draft five generic jobs: set up or update a repository, deliver an objective without babysitting, merge verified changes safely, run many agents in parallel, and research an experience to inform product decisions. Learning from corrections is cross-cutting, not another job. Setting up a named consumer repository is an instance of the setup job, never a product-specific jfactory job.

The owner requested standing goals and proof requirements next, then confirmed [the complete contract](../outcomes/README.md) on 2026-10-01. It distinguishes executable controls from pending model trials. The detailed proof recipes are agent-authored translations; neither the earlier interview nor the confirmation is a claim that the owner inspected each row or that the workflow meets every goal. Owner-requested release stays supporting guidance, with no new release authorization. Behavioral and blinded cross-model trials remain pending.

At the owner's request, the contract was informed by Lauren Tan's pinned pstack verification skills and supporting principles. [The method sources and adaptations](../outcomes/README.md#method-sources-and-adaptations) distinguish original methods from jfactory's own scope and authorization. The added goals and trial cases are not completed trials or an upstream update; vendor files remain unchanged.

On 2026-10-01 the owner confirmed speed, resource efficiency and predictable progress across the jobs. [Speed](../outcomes/README.md#speed-and-its-measurement) means end-to-end time to a verified result with waiting and rework visible, not skipped proof. [Efficiency and progress](../outcomes/README.md#resource-efficiency-and-predictable-progress) require proportionate resource use and a resumable account of actual state. No numeric target, new priority order or measured improvement has been agreed or established. Consumer adoption is separate and was explicitly excluded from this work.

## Next objective

Task location: GitHub issues in this repository labelled `jfactory-objective`

[#22 Run blinded cross-model evals of jfactory setup](https://github.com/jordymarshall/jfactory/issues/22): agreed, not started.
