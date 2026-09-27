# jstack

A portable engineering workflow: agree on an objective, implement and verify against observable acceptance criteria, preserve evidence, and deliver a pull request.

Built around selected [Lauren Tan pstack](https://github.com/cursor/plugins/tree/ecc249f1e306fc64ddf83c7bed16cacf7c2239db/pstack) skills, with repository adoption, explicit verification scopes and PR-first delivery. Upstream source remains pinned and unchanged with its MIT license and hash receipt. This is an independent adaptation, not an official Cursor or OpenAI plugin.

## Use in a project

Tell your coding agent:

> Adopt the engineering workflow from https://github.com/jordymarshall/jstack in this repository. Inspect the README and installer first, install the skill, preserve existing instructions, then follow jstack's repository setup. Establish our objective and real application verification. Deliver changes as a PR; use a draft if required evidence is blocked.

Or inspect a checkout, then install with Python 3.10+:

```sh
git clone https://github.com/jordymarshall/jstack.git /tmp/jstack
python3 /tmp/jstack/scripts/install.py /path/to/project
```

The default installer copies the self-contained bundle into `.agents/skills/jstack` and adds a small managed section to root `AGENTS.md`. It preserves surrounding text, refuses conflicting local modifications, and records payload hashes and the source commit. Repeating the same installation is safe. Updating requires a reviewed source checkout and `--update`; locally modified managed files still cause a refusal. No remote shell pipe, automatic dependency installation, credentials, commits, pushes or deployment.

`--agent claude` uses `.claude/skills/jstack` and `CLAUDE.md`; `--agent cursor` uses `.cursor/skills/jstack` and `AGENTS.md`. These installation layouts are tested; actual model behavior and those hosts' runtime integrations must be verified in your project. Other agents can read [SKILL.md](skills/jstack/SKILL.md) directly. Reload/start a fresh agent session after adoption and confirm it sees the instructions.

## How work proceeds

1. Inspect existing code, decisions, tests and CI. Clarify unresolved intent; reuse the project's product process.
2. Record a bounded outcome and observable acceptance criteria in the existing task.
3. Map required verification scopes before implementation. A component fixture cannot prove an authenticated application journey.
4. Implement, execute checks, inspect results and side effects, and correct failures autonomously inside that scope.
5. Update affected canonical records, review the diff and open a PR. Use a draft when required proof is missing. Merge and deployment require separate authorization.
6. Improve recurring weaknesses through tests/types/lints and behavioral skill evals, not an ever-growing instruction file.

The [verification contract](skills/jstack/references/verification.md) includes optional command receipts. They reject failed, stale and insufficient-scope evidence mechanically, but do not judge whether the test itself is meaningful. Real UI/CLI/API interactions and side-effect assertions remain the project's responsibility.

## What this does not promise

- Installing instructions does not guarantee an agent follows them or make an application correct.
- No application-specific tests, customer hypotheses, production credentials or business documents are bundled.
- No background daemon, automated merge, production deployment, or remote branch protection is configured.
- No universal model benchmark or cross-model reliability claim. `evals/scenarios.md` provides realistic evaluation cases; model trials must be run and inspected separately.
- Python command capture is POSIX-only; use WSL or host-native tools on Windows. Installation tests do not demonstrate macOS/Claude/Cursor runtime behavior.

## Develop and verify jstack

```sh
python3 -m unittest discover -s tests -v
python3 skills/jstack/scripts/check-upstream.py
```

Tests exercise non-destructive installation, updates, failure capture, stale evidence and component/application scope separation. CI runs these checks on PRs. Changes to the workflow itself should also use the bundled pstack eval playbook with actual tool transcripts and artifacts. A passing packaging test is not a behavioral eval.

## Attribution and updates

Original pstack files: copyright Lauren Tan 2026, MIT, version 0.15.5 at `ecc249f1e306fc64ddf83c7bed16cacf7c2239db`. See [upstream provenance](skills/jstack/vendor/pstack/UPSTREAM.md) and [license](skills/jstack/vendor/pstack/LICENSE). jstack additions are MIT, copyright Jordan Marshall 2026.

Update upstream in a separate checkout, review its diff and compatibility, retain the original license, regenerate the receipt from original bytes and run integrity/behavior checks. Never silently follow upstream main or customize the vendored originals in place.
