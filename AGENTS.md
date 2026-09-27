# Working on jfactory

jfactory contains a portable engineering methodology and tools, not an application or customer product brief. Preserve upstream pstack attribution and original bytes. Keep repository-specific business context out of the distributed bundle.

Use [jfactory](skills/jfactory/SKILL.md) for changes here. Default delivery is a PR against main, with passing applicable checks and explicit evidence limits. The owner authorizes protected squash auto-merge for this repository after applicable verification passes. Require PRs and the GitHub Actions `checks` job against the latest main, with no rule bypass. The desired [main ruleset](.github/rulesets/main.json) records these settings; verify it is active remotely before queuing auto-merge. Enabling the repository auto-merge setting alone does not establish protection. Keep shared branches current by merging main into them, rerun affected checks, and refresh overlapping PRs after each merge. Do not push the base branch directly or bypass gates.

Run `python3 -m unittest discover -s tests -v` and `python3 skills/jfactory/scripts/check-upstream.py`. Test installer changes in disposable repositories, preserving user files and rejecting conflicting updates. Test verification changes with failure/staleness/scope negative controls. Skill behavior needs separate model trials; never describe unit checks as a full workflow eval.

The entry point lives in `skills/jfactory/SKILL.md`, detailed procedures in its `references/`, executable checks in its `scripts/`, installation in `scripts/install.py`, and behavioral evaluation cases in `evals/scenarios.md`.
