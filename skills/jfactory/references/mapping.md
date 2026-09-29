# Map the repository for verification

`.jfactory/verification.json` decides what every PR runs. An accurate map means a PR verifies the areas it touched and nothing else. A gap makes a change verify every feature, and a vague map makes agents guess. Follow these steps in order during setup, and again when the product changes shape. Each step ends with a command whose output you can check. The [example mapping](../templates/verification.example.json) shows the finished result.

Commands below use `VP` for the installed script: `VP="python3 <bundle>/scripts/verify_plan.py"`.

## 1. Inventory what exists

Run `$VP inventory` (add `--depth 3` for deep trees). It lists every directory with its tracked file count and how each is mapped so far. Read the routes, pages, commands and API handlers behind the directories; the directory names alone are not enough. Note generated, vendored and fixture directories.

## 2. Name features from what users do

A feature is something a user or the owner would recognise: "save a brief", "sign in", "export invoices", "the `init` command". List each with how a user reaches it: the route or command, navigation, and a stable selector. Take the list from the product brief and the app's navigation, not from the folder layout. Confirm it with the owner in one question: "These are the areas I will verify separately. Anything missing or wrongly merged?"

## 3. Give each feature its paths

For each feature, list its own code: route or page directories, feature-specific server and library code, and its own tests and journey specs. Prefer directory globs such as `app/src/app/briefs/**`. A file may belong to several features when it serves each of them directly.

Do not map a catch-all such as `src/**` to a feature that runs journeys. Then every change would run that feature's journeys, which is the problem this map exists to prevent. `audit` warns when one feature covers most of the code.

## 4. Map shared code without pulling in every journey

Code that many features use gets its own feature, with checks proportionate to it:

| Shared area | Feature and suites |
| --- | --- |
| Data layer, API client, utilities | `shared-data`: unit and integration tests, plus the short smoke journey |
| Auth and session library | The `sign-in` feature, whose journey exercises it |
| Design system components | `design-system`: component and visual tests, not every journey |
| Package manifests, lockfiles, build and framework config, the smoke spec | `build-and-dependencies`: build, unit and smoke |

The nightly `ci --all` run covers every journey, so a shared change is still exercised in full. It just doesn't hold a PR for 45 minutes. When a shared change is risky for one specific journey, the objective names that journey and the implementer runs it.

## 5. Mark what cannot change behavior as static

Put only files that cannot change runtime or agent behavior in `static`: prose docs, license, changelog, images used only in docs. Agent instructions, skills, verification recipes and CI config are never static, even though some are Markdown. Gate files (`.jfactory/`, `.github/workflows/`, `.github/rulesets/`) are handled automatically. Changing them needs a full verdict and runs only `always_suites` and `full_suites`.

## 6. Define suites that can run alone

Every suite a feature names is defined under `suites` with its command, its measured minutes and, if it needs a running app, its target:

```json
"browser-briefs": {"run": "npx playwright test e2e/briefs.spec.ts", "minutes": 4, "target": "local"}
```

Give each feature its own journey suite: one spec file, a tag (`--grep @briefs`) or a Playwright project. Add a `smoke` suite of one or two minutes that loads the app and signs in. Keep `always_suites` and `full_suites` to fast whole-repository checks such as lint, types and unit tests. Time each suite with `$VP ci --suites <name>` and record the minutes it reports.

## 7. Define where the app runs, and prove it starts

Under `targets`, record each place verification runs the app:

- `setup`: installs dependencies in a fresh checkout.
- `doctor`: fails with a clear message when a tool, variable or service is missing.
- `start`: starts the app on `$PORT`. A deployed target, such as the PR preview, uses `url` instead.
- `ready`: a URL that answers once the app is up.
- `probe`: an optional short check, such as the smoke spec.
- `auth`: how verification signs in: a seeded test account, a stored session, a bypass token for a protected preview, or `none`.

Suites with a `target` get `$PORT` and `$BASE_URL`, and `ci` starts and stops the app around them.

Then prove it in the place that matters: a new workspace (for Conductor, a new cloud workspace, as a verifier gets) and the CI runner. Run `$VP smoke --target local --fresh --record .jfactory/smoke.json`. It runs setup, doctor, start, the readiness URL and the probe, then stops the app and records which step failed and why. Fix what it reports, usually a missing secret, service, browser binary or sign-in. Rerun until it passes, and commit the receipt. A target that needs a human sign-in with no stored session or test account stays `blocked` with that owner step. `setup_check.py` will not accept `Verification: verified` until every target has a passing receipt.

## 8. Set risk levels and the budget

Give every feature `"verify": "independent"` or `"ci"` using the [verification contract](verification.md#change-aware-verification-and-the-merge-gate), and confirm them with the owner. Propose a per-PR budget, usually 10 to 15 minutes, confirm it and record `pr_budget_minutes`. A feature that truly cannot fit, such as checkout with payment journeys, gets an owner-approved `budget_minutes`.

## 9. Audit until clean and show the owner

Run `$VP audit` and fix every FAIL, then the warnings. Then run `$VP plan --files <path>` for one typical file per feature, a shared file, the lockfile and a doc. Put a table of those plans (suites and minutes) in the adoption PR, so the owner sees what a typical PR will run.

Install [the change-aware CI job](../templates/jfactory-checks.yml): it runs `audit`, then only the planned suites on PRs, and every suite nightly. Add the project's runtime steps, matching the local target's `setup`, and make its `checks` job required.

## Keep the map current as the product changes

- **Every PR.** `ci` fails when a tracked file matches no feature, or a feature matches no file. So a new area or a deleted one is mapped in the same PR that creates it. A mapping change is a gate change, so the independent verifier reviews it: the new paths, suites and level must fit what the code does.
- **Timings.** `ci` reports when a suite ran over 1.5 times its recorded minutes; update `minutes` then.
- **Nightly.** `ci --all` runs every suite, catching regressions in journeys that PRs didn't touch. A nightly failure becomes a fix objective.
- **Larger product changes.** After a redesign, a new product area or a reorganised codebase, rerun steps 1 to 9 for the affected areas and rerun `smoke`. Re-running setup does this.
