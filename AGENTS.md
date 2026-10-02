# Working on jfactory

## Product brief

jfactory is a portable engineering methodology and toolset for coding agents, not an application. It is for the owner first, then any developer who points their coding agent at this repository. It removes four pains:

- babysitting agents with "keep going" (the primary one);
- agents calling work done when it isn't right: unproven, or proven only against checks that miss the outcomes, the job goals or the standards;
- reviewing every PR by hand;
- coordinating many agents in parallel.

The principle behind all of it: done means right. Work that passes its checks but misses the outcomes, the job goals or the standards is not done.

Success is measured in this order:

1. Setup plus a first feature reach a verified, merged PR with the owner only answering product questions.
2. Agent PRs merge without owner fixes.
3. Blinded cross-model evals show it helps.

Non-goals:

- Anything that works for only one repository or product. jfactory must set up and improve any repository, so product facts belong in each project's own files, never in the bundle.
- Releasing production on its own.

Routines and scheduled automation are acceptable where they help. Preserve upstream pstack attribution and original bytes. The owner's answers are in the [setup record](.jfactory/setup.md#owner-interview). Outcomes, measures and one document per job to be done are in [outcomes/](outcomes/README.md); what good looks like per dimension is in the [standards map](.jfactory/standards.md).

## System map

The entry point is [skills/jfactory/SKILL.md](skills/jfactory/SKILL.md), with procedures in its `references/`, executable checks in its `scripts/` (`verify_plan.py`, `coord.py`, `usage.py`, `evidence.py`, `feedback.py`, `check-upstream.py`), templates in `templates/`, the UX skill in `skills/jfactory-ux/` and pinned pstack sources in `vendor/pstack/`. `scripts/install.py` copies that bundle into consumer repositories. `tests/` covers the scripts, with simulated `gh`, `git` and `conductor` in `tests/fakes/`. [evals/scenarios.md](evals/scenarios.md) holds behavioral evaluation cases. The bundle does not deploy applications, and merging to main deploys nothing.

## Feature/status map

[.jfactory/verification.json](.jfactory/verification.json) maps paths to features, recipes and CI suites. The [setup record](.jfactory/setup.md) holds current readiness, evidence and open decisions.

## Agent instructions

Use [jfactory](skills/jfactory/SKILL.md) for changes here. Objectives live in GitHub issues labelled `jfactory-objective`, using [the objective template](skills/jfactory/templates/objective.md); small fixes can state theirs in the PR. Default delivery is a ready-for-review PR against main, with passing applicable checks and explicit evidence limits. The owner authorizes protected squash auto-merge after applicable verification passes and merging deploys nothing. The desired [main ruleset](.github/rulesets/main.json) requires PRs, squash merges, and both the `checks` job against the latest main and the `jfactory verified` status. Before queuing auto-merge, confirm which of these are active remotely; the setup record lists the current state. Enabling the repository auto-merge setting alone does not establish protection. Keep shared branches current by merging main into them, rerun affected checks, and refresh overlapping PRs after each merge. Do not push the base branch directly or bypass gates.

Before setup and objective/goal definition, read the complete bundled [grilling skill](skills/jfactory/skills/grilling/SKILL.md), then reuse settled answers. Before change and PR explanations, feedback and choices needing understanding, read the complete [show-me skill](skills/jfactory/skills/show-me/SKILL.md). Both include their full pinned upstream method and jfactory integration. Keep product, engineering and UI/UX intent and job goals in canonical project documentation for verifiers.

Run `python3 -m unittest discover -s tests -v` and `python3 skills/jfactory/scripts/check-upstream.py`, and after setup or instruction changes `python3 skills/jfactory/scripts/setup_check.py --remote`; CI also runs `tests/browser_smoke.py` and `tests/dashboard_smoke.py`. Test installer changes in disposable repositories, preserving user files and rejecting conflicting updates. Test verification changes with failure/staleness/scope negative controls. Skill behavior needs separate model trials; never describe unit checks as a full workflow eval. Keep links inside `skills/jfactory` resolvable within the installed bundle; `tests/test_links.py` enforces it.
