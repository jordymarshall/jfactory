# jfactory setup record

This repository is jfactory's own source. It uses the bundle in place through [AGENTS.md](../AGENTS.md) instead of an installed copy, so there is no installation receipt; the loaded version is the checked-out commit. Re-running setup updates this record rather than adding another. `skills/jfactory/scripts/setup_check.py --remote` checks it.

## Readiness

Last reviewed 2026-09-28 against `main` at `6ae1299`.

| Area | State | Evidence or reason |
| --- | --- | --- |
| Documentation | verified | `AGENTS.md` has the four entry sections, and `tests/test_links.py` passes. The README explains the components, loop routing, objectives, verification, auto-merge, coordination and the correction ladder. Its six diagrams are PNG images rendered from `docs/diagrams/*.mmd`, so they show in GitHub's mobile app; a test keeps them in sync with their sources. |
| Product direction | verified | The owner answered every interview question below on 2026-09-28. The brief in `AGENTS.md` follows those answers. |
| Workspace tools | verified | Python 3 only; the browser smokes also need Node, Chrome and Playwright's ffmpeg. In the Conductor cloud workspace (Python 3.9.25, Node 24.14.1), the unit tests, `check-upstream.py`, `tests/browser_smoke.py` and `tests/dashboard_smoke.py` passed. CI runs Python 3.10. No cloud setup script is needed. |
| Verification | verified | `.jfactory/verification.json` maps every tracked file except the gate paths, which always need full verification. `setup_check.py` confirms it and the `jfactory verified` workflow. |
| Environments | not applicable | Nothing deploys. |
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

None. (Requiring `jfactory verified` on main was applied by the owner on 2026-09-28.)

## Next objective

Task location: GitHub issues in this repository labelled `jfactory-objective`

[#22 Run blinded cross-model evals of jfactory setup](https://github.com/jordymarshall/jfactory/issues/22): agreed, not started.
