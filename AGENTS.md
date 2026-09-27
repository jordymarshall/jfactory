# Working on jfactory

jfactory contains a portable engineering methodology and tools, not an application or customer product brief. Preserve upstream pstack attribution and original bytes. Keep repository-specific business context out of the distributed bundle.

Use [jstack](skills/jstack/SKILL.md) for changes here. Default delivery is a PR against main, with passing applicable checks and explicit evidence limits. This repository is an explicit exception to the consumer auto-merge default: leave jfactory's own PRs open for owner review. Do not enable auto-merge or merge them without a separate request. Enabling the repository setting only makes the option available. Do not push the base branch directly or bypass gates.

Run `python3 -m unittest discover -s tests -v` and `python3 skills/jstack/scripts/check-upstream.py`. Test installer changes in disposable repositories, preserving user files and rejecting conflicting updates. Test verification changes with failure/staleness/scope negative controls. Skill behavior needs separate model trials; never describe unit checks as a full workflow eval.

The entry point lives in `skills/jstack/SKILL.md`, detailed procedures in its `references/`, executable checks in its `scripts/`, installation in `scripts/install.py`, and behavioral evaluation cases in `evals/scenarios.md`.
