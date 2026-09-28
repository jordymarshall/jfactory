# Working on jfactory

## Product brief

jfactory is a portable engineering methodology and toolset for coding agents, not an application. Its customers are repository owners who want an agent to take a bounded outcome from agreement to a verified, merged PR without being told to "keep going", while the owner keeps product decisions and production releases. Hypothesis: explicit objectives, change-aware verification by a different model family and protected auto-merge let owners delegate more work with less review. Non-goals: bundling any customer's product brief, business context, credentials or release permissions; a background supervisor or scheduler. Preserve upstream pstack attribution and original bytes.

## System map

The entry point is [skills/jfactory/SKILL.md](skills/jfactory/SKILL.md), with procedures in its `references/`, executable checks in its `scripts/` (`verify_plan.py`, `coord.py`, `usage.py`, `evidence.py`, `check-upstream.py`), templates in `templates/`, the UX skill in `skills/jfactory-ux/` and pinned pstack sources in `vendor/pstack/`. `scripts/install.py` copies that bundle into consumer repositories. `tests/` covers the scripts, with simulated `gh`, `git` and `conductor` in `tests/fakes/`. [evals/scenarios.md](evals/scenarios.md) holds behavioral evaluation cases. Nothing here deploys.

## Feature/status map

[.jfactory/verification.json](.jfactory/verification.json) maps paths to features, recipes and CI suites. The [setup record](.jfactory/setup.md) holds current readiness, evidence and open decisions.

## Agent instructions

Use [jfactory](skills/jfactory/SKILL.md) for changes here. Default delivery is a ready-for-review PR against main, with passing applicable checks and explicit evidence limits. The owner authorizes protected squash auto-merge for this repository after applicable verification passes. Merging deploys nothing (`merge_deploys: none`). The desired [main ruleset](.github/rulesets/main.json) requires PRs, squash merges, and both the `checks` job against the latest main and the `jfactory verified` status. Before queuing auto-merge, confirm which of these are active remotely; the setup record lists the current state. Enabling the repository auto-merge setting alone does not establish protection. Keep shared branches current by merging main into them, rerun affected checks, and refresh overlapping PRs after each merge. Do not push the base branch directly or bypass gates.

Run `python3 -m unittest discover -s tests -v` and `python3 skills/jfactory/scripts/check-upstream.py`; CI also runs `tests/browser_smoke.py` and `tests/dashboard_smoke.py`. Test installer changes in disposable repositories, preserving user files and rejecting conflicting updates. Test verification changes with failure/staleness/scope negative controls. Skill behavior needs separate model trials; never describe unit checks as a full workflow eval. Keep links inside `skills/jfactory` resolvable within the installed bundle; `tests/test_links.py` enforces it.
