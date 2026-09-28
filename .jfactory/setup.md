# jfactory setup record

This repository is jfactory's own source. It uses the bundle in place through [AGENTS.md](../AGENTS.md) instead of an installed copy, so there is no installation receipt; the loaded version is the checked-out commit. Re-running setup updates this record rather than adding another.

## Readiness

Last reviewed 2026-09-28 against `main` at `7c83999`, plus the setup PR that adds this record.

| Area | State | Evidence or reason |
| --- | --- | --- |
| Documentation | verified | `AGENTS.md` has the four entry sections. `tests/test_links.py` passes. The contradictions found by a script-against-docs audit are reconciled in the setup PR. |
| Product direction | configured but unverified | The brief in `AGENTS.md` is the agent's summary of the README and history. The owner has not confirmed it. |
| Workspace tools | verified | Python 3 only; the browser smokes also need Node, Chrome and Playwright's ffmpeg. In the Conductor cloud workspace (Python 3.9.25, Node 24.14.1), all 80 unit tests, `check-upstream.py`, `tests/browser_smoke.py` and `tests/dashboard_smoke.py` passed. CI runs Python 3.10. No cloud setup script is needed. |
| Verification | verified | `.jfactory/verification.json` maps every tracked file except the gate paths, which always need full verification. `verify_plan.py plan --files "$(git ls-files \| paste -sd, -)"` reports no other unmapped files. The browser smokes cover the UX helpers. |
| Environments | not applicable | Nothing deploys. |
| PR delivery | blocked on an owner decision | Repository auto-merge is on. The active remote ruleset "Verified squash merges to main" (id 24086594) requires PRs, squash merges and `checks` against the latest main, with no bypass actors. It does not require `jfactory verified`, which [the committed ruleset](../.github/rulesets/main.json) also lists. The `jfactory verified` workflow runs on every PR either way. `merge_deploys` is `none` in `coordination.json`. |
| Coordination | verified | `gh` has admin access and the `jfactory-program` and `jfactory-hold` labels exist. `conductor auth whoami` succeeds. The usage reader reads Claude usage; Codex usage stays unknown until a Codex session runs here. |

## Open owner decisions

1. **Require `jfactory verified` on main?** The committed ruleset and the docs say yes; the active ruleset does not. Recommendation: import the committed ruleset (Settings → Rules → Rulesets), so a non-static PR cannot merge without a verdict from another model family. Until then, agents post the verdict anyway and state in the PR that it is not enforced.
2. **Confirm the product brief** in `AGENTS.md`.

## Next action

Once decision 1 is settled, update the PR delivery row. Next proposed objective: run one evaluation from `evals/scenarios.md` (for example "Setup jfactory" on an existing repository) with blinded candidates, to get the first behavioral evidence.
