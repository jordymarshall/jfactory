# Map the repository for verification

`.jfactory/verification.json` decides what every PR runs, together with the coverage that whole-suite runs record. An accurate map means a PR verifies the areas it touched and nothing else. A gap makes a change verify every feature, and a vague map makes agents guess. Follow these steps in order during setup, and again when the product changes shape. Each step ends with a command whose output you can check. The [example mapping](../templates/verification.example.json) shows the finished result.

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

Most files don't belong to exactly one screen, and you don't have to guess which journeys they affect. The paths you map are the floor, and recorded coverage finds the rest:

- **Recorded coverage.** Each whole-suite run (`ci --all --impact-out`, see [step 8](#8-set-risk-levels-and-when-the-whole-suite-runs)) records which tracked files each suite actually executed. On a PR, `ci --impact` adds every suite that executed a changed file. A change to `lib/db.ts` then runs exactly the journeys that use it, whether that is two or twelve. Coverage only adds suites, never removes one the map requires. A new file that coverage hasn't seen yet falls back to its mapped feature until the next whole-suite run. See [step 6](#6-define-suites-that-can-run-alone) for recording it.
- **Test-impact selection inside a suite.** A command that picks tests from the changed files, such as `jest --findRelatedTests`, `vitest related`, `nx affected` or `pytest --testmon`, narrows unit and integration suites the same way.
- **Several features.** List a file under each feature it directly serves; the plan runs each of their journeys.

So shared code needs only its own fast checks in the map. Recorded coverage supplies the journeys, and the whole-suite run covers anything coverage cannot see, such as config read at build time.

## 5. Mark what cannot change behavior as static

Put only files that cannot change runtime or agent behavior in `static`: prose docs, license, changelog, images used only in docs. Agent instructions, skills, verification recipes and CI config are never static, even though some are Markdown. Gate files (`.jfactory/`, `.github/workflows/`, `.github/rulesets/`) are handled automatically. Changing them needs a full verdict and runs only `always_suites` and `full_suites`.

## 6. Define suites that can run alone

Every suite a feature names is defined under `suites` with its command, its measured minutes and, if it needs a running app, its target:

```json
"browser-briefs": {"run": "npx playwright test e2e/briefs.spec.ts", "minutes": 4, "target": "local"}
```

Give each feature its own journey suite: one spec file, a tag (`--grep @briefs`) or a Playwright project. A PR runs a feature's journey suite only when it changes a file users can see; a change only to `backend_paths` (server logic, data, APIs) runs it after merge instead ([scope](verification.md#change-aware-verification-and-the-merge-gate)). Small suites let coverage select precisely and parallel jobs balance evenly. Add a `smoke` suite of one or two minutes that loads the app and signs in. Keep `always_suites` and `full_suites` to fast whole-repository checks such as lint, types and unit tests. Time each suite with `$VP ci --suites <name>` and record the minutes it reports.

For recorded coverage, each suite writes a coverage report into `$JFACTORY_COVERAGE_DIR` while it runs. `ci` reads Istanbul `coverage-final.json`, V8 coverage, coverage.py `coverage json` output or a plain list of paths:

- **Node server code:** `ci` sets `NODE_V8_COVERAGE` for the suite and its target, so Node writes coverage automatically when it exits. The server must exit cleanly on SIGTERM.
- **Browser code:** collect Playwright's `page.coverage` or an Istanbul-instrumented build (for example `monocart-reporter`), with source maps resolved to repository paths, and write it to that directory.
- **Python services:** run them under `coverage run` and write `coverage json` there.

Check a whole-suite run's output: `ci` names suites that recorded no coverage.

### Journeys a model drives

Some projects write journeys as goals in plain language that a model carries out, for example with [e2e](https://github.com/tester-army/e2e) (`npx e2e init`; web and mobile), Stagehand or Midscene. These suites are flexible, but a model is neither deterministic nor free. Keep them trustworthy this way:

- **Pair every model-driven step with an exact check.** After "upgrade the workspace to Pro", assert the status text says Pro. The model reaching its goal is a claim; the assertion is the proof.
- **Judge meaning, not wording.** Assert that a result contains "Pro", not that it matches a sentence a model wrote, so the suite survives a model change.
- **Replay recorded actions on PRs.** Record a step's actions only after its check passes, and replay them on later runs without calling the model. In CI, replay read-only from committed recordings, so the PR gate is fast, free and repeatable. A step that calls the model there has a stale recording: re-record it. e2e does this with its replay cache (`cache: 'read-write'` locally; read-only when `CI` is set).
- **Keep live-model runs off the gate.** Mark a suite that calls a live model on every run `"live_model": true`. `plan` and `ci` never run it on a PR, not even in a whole-suite run. [The scheduled workflow](../templates/jfactory-live-suites.yml) runs it weekly with `ci --live` and opens an issue when it fails. `setup_check.py` fails when the map has live suites and no scheduled workflow runs them. It reads workflows line by line, so write that job in ordinary block style: a job or step condition it cannot confirm holds on a schedule, a merge key or a flow-style mapping (`{...}`) is reported as unconfirmed rather than accepted. The independent verifier may still run one by hand when the change needs it.
- **Retry only what a retry can fix.** A configuration or credential error fails the same way every time, so fix it rather than retrying. An app or provider that was briefly unavailable may pass on one retry. e2e's exit codes separate the two: 2 for configuration, 3 for the environment.

Install such a tool in the project, with its own skill if it ships one, not inside the jfactory bundle.

The default is simpler: setup writes [goal tests](goal-tests.md), which are ordinary Playwright specs that an agent writes from each job document's key goals. They need no model in CI. A model-driven tool is an optional add-on.

Set `shards` to the number of parallel CI jobs. `ci --shard I/N` runs its share of the planned suites, balanced by recorded minutes, so a 40-minute plan across four jobs takes about 10 minutes of waiting. It still uses 40 minutes of compute.

## 7. Define where the app runs, and prove it starts

Under `targets`, record each place verification runs the app:

- `setup`: installs dependencies in a fresh checkout.
- `doctor`: fails with a clear message when a tool, variable or service is missing.
- `start`: starts the app on `$PORT`. A deployed target, such as the PR preview, uses `url` instead.
- `ready`: a URL that answers once the app is up.
- `probe`: an optional short check, such as the smoke spec.
- `auth`: how verification signs in: a seeded test account, a stored session, a bypass token for a protected preview, or `none`.
- `seed`: creates this run's own test data, named by `$JFACTORY_RUN_ID`, such as a fresh test account or workspace with a few records.
- `cleanup`: removes this run's data. It runs after every suite, including failed ones.
- `prune`: removes data that interrupted runs left behind, and only data older than a few hours, since parallel jobs may still be using newer records. A whole-suite run calls it before its journeys.

Suites with a `target` get `$PORT`, `$BASE_URL` and `$JFACTORY_RUN_ID`, and `ci` starts the app, seeds, runs the suite, cleans up and stops the app.

Never point journeys at one shared, long-lived test account. Every run adds records, nothing removes them, and pages slow down until checks time out for reasons unrelated to the change. In one real case, a shared account piled up about 1,700 briefs from many tests. The Briefs page showed them all at once, and an accessibility scan of that one page took 21 of a 45-second timeout. Per-run data keeps each journey's starting state small and known, and parallel jobs can't see each other's records. `audit` warns about a target with journeys but no `seed`, `cleanup` or `prune`. When a journey needs a large dataset, for example to test paging, seed that size deliberately in that journey. A symptom like that one is also a product finding: real users with many records hit the same page. Raise it as an objective rather than hiding it with test data.

Then prove it in the place that matters: a new workspace (for Conductor, a new cloud workspace, as a verifier gets) and the CI runner. Run `$VP smoke --target local --fresh --record .jfactory/smoke.json`. It runs setup, doctor, start, the readiness URL, seed, the probe and cleanup, then stops the app and records which step failed and why. A failed setup, doctor or seed step, a start command that exits on its own, and any step that exits with code 2 are setup failures and are never retried. An app that doesn't answer in time, or a probe or cleanup that fails otherwise, is an environment failure and is retried once. Make a probe exit 2 when it finds a configuration problem. The receipt records which kind it was. Fix what it reports, usually a missing secret, service, browser binary or sign-in. Rerun until it passes, and commit the receipt. A target that needs a human sign-in with no stored session or test account stays `blocked` with that owner step. `setup_check.py` will not accept `Verification: verified` until every target has a passing receipt.

## 8. Set risk levels and when the whole suite runs

Give every feature `"verify": "independent"`, `"review"` or `"ci"` using the [verification contract](verification.md#change-aware-verification-and-the-merge-gate), and confirm them with the owner. Keep `independent` for risky areas: money, sign-in and permissions, stored data and migrations, security, external side effects and releases. Agent instructions are gate files, which always keep a verdict. Under the default [minimum gates](#minimum-gates), mark every other feature `ci` with `"screens": false`: it merges on green static CI, and its screens are checked by the whole-suite run. When the owner chooses fuller per-PR checks, mark other features with screens `review` instead, so they get one strategic review with screenshots, and keep `ci` for code with no screens. Mark a feature with screens but no journey suite yet `"screens": true`. Mark a feature `"screens": false` when it lists a journey suite but has no screens of its own, such as a release or infrastructure feature whose smoke journey only checks that the app still works. Its suites still run when the plan selects them, but the gate asks for no walkthrough or screenshots.

Then ask the owner when the **whole suite** runs, and record the answer as `"full_suite"`. Every other run executes only the suites the change needs. The whole suite catches what the map and coverage miss, and refreshes recorded coverage, but browser journeys cost time and compute: show the owner its measured total (the sum of every suite's `minutes`) and how often each option would run it:

| `full_suite` | The whole suite runs | Suits |
| --- | --- | --- |
| `on-request` | Only on the `full-suite` PR label (`full_suite_label` renames it) or a manual run, for example on the final PR of a major feature | Long browser suites, a shared test account, or limited CI minutes |
| `nightly` | Every night, plus the label | Fast suites and plenty of CI capacity |
| `merge` | After every merge to the base branch, plus the label | Few merges a day and a need to catch integration breaks quickly |
| `every-pr` | On every PR | Only when the whole suite takes a few minutes |

`audit` gives jfactory's recommendation with its reason; present it as the recommended option. It suggests `on-request` while any suite has no measured `minutes`, since the cost is then unknown, and when journeys share one account's data (no `seed`/`cleanup`), because a whole-suite run then blocks every other run and piles up data. Otherwise it suggests `every-pr` for a whole suite of about 5 minutes or less, `nightly` when the parallel wait is about 15 minutes or less, and `on-request` beyond that. Adjust for what the map can't see, such as how many PRs merge a day or a tight CI budget. `verify_plan.py full-suite --event <event> --labels <labels>` turns the choice into `mode=full|planned|skip` for CI, and [the change-aware CI job](../templates/jfactory-checks.yml) uses it. `audit` warns while the owner hasn't chosen, and the default until then is `nightly`. With `on-request`, add the label to the PR that completes a major feature and before a release; recorded coverage then refreshes only on those runs.

### Minimum gates

The default for new setups ([verification.example.json](../templates/verification.example.json)), because every per-PR job multiplies by every push of every worker. PRs and base-branch pushes run only `always_suites` (types, lint, related unit tests): set `"pr_journeys": false`. Journeys run on the `full_suite` schedule (`nightly`; `audit` refuses `on-request` with `pr_journeys` false). Only the risky features keep `"verify": "independent"` (money, sign-in and permissions, stored data and migrations, security, external side effects and releases); split a feature whose screens and stored-data logic share paths, as the example map does with `save-brief` and `brief-storage`. Mark the rest `"verify": "ci"` and `"screens": false`, and set `"force_independent": false` so a test or standards-document edit (a job document, the brand guide) follows its feature's level instead of forcing a verdict. Agent instructions at any depth always keep their verdict, and so do gate files such as `.jfactory/standards.md`. Fuller per-PR checks are an owner choice when CI capacity allows; record it with its trade-off. Gate files still need a verdict. Trade-off: a screen-only break can ship before the next whole-suite run reports it. See [queue operations](ci-runners.md#queue-operations-fewer-jobs-before-more-machines).

There is no default time limit. Precision comes from the map plus recorded coverage, and speed from parallel jobs, so a PR runs what its change needs without trading away checks. The one structural rule, enforced by `audit`, is that the map never makes journey suites run on every PR: `always_suites` and `static_suites` contain no suite with a `target`. Running the whole suite on every PR is a separate, explicit owner choice (`"full_suite": "every-pr"`). If the owner wants a cap anyway, show the measured numbers (each feature's plan, a shared-code change's plan and the parallel wait) and record their choice as `pr_budget_minutes`. `audit` then warns about changes over it; it never skips a required check.

### Link each feature to its job to be done

A feature users see names its job document: `"outcome": "outcomes/plan-a-campaign-brief.md"` (see [setup](setup.md#record-the-sources-of-truth-verifiers-check-against) and [the template](../templates/outcome.md); `"journey"` is read too). The document says what the user is trying to do and how each standing goal is proven. The suites here are how most of those proofs run. `audit` warns about a feature with screens and no outcome document, fails on a path that isn't tracked, and warns about goals without a proof. Outcome and standards documents are never `static`: map them to their feature. With fuller per-PR checks, edits to them always get the independent verifier; under the default minimum gates they follow their feature's level, so a risky feature's documents get it and a `ci` feature's do not.

## 9. Audit until clean and show the owner

Run `$VP audit` and fix every FAIL, then the warnings. Then run `$VP plan --files <path>` for one typical file per feature, a shared file, the lockfile and a doc. Put a table of those plans (suites, total minutes and parallel wait) in the adoption PR, so the owner sees what a typical PR will run.

Install [the change-aware CI job](../templates/jfactory-checks.yml). On PRs it runs `audit`, then the planned suites plus those that recorded coverage selects, across parallel jobs. It runs every suite and records coverage when the owner's `full_suite` choice says so. Add the project's runtime steps, matching the local target's `setup`, and make its `checks` job required.

## Keep the whole suite fast

A whole-suite run should take minutes, not an hour. Measure before changing anything: time each spec file from a whole-suite run's report, and compare the same tests across runs. When the same tests get slower week by week, suspect accumulated test data, and confirm it before acting: count the records the slow pages load, then compare a run on a small, known dataset. Application changes, dependencies, runner contention and slow external services can also slow unchanged tests.

- **Parallel jobs by spec file.** Split spec files across CI jobs, balanced by their measured minutes, and let each job run every viewport for its own files. With one shared account this is safe only when the same spec never runs twice at once, and when specs avoid account-wide sweeps ("archive every brief named X"), fixed primary keys and read-modify-restore of account settings. Fix or isolate those specs first.
- **One database copy per CI job, never one shared queue.** Browser and journey suites that share one test database and account must run one at a time, so PRs wait in a queue for hours. Where the database supports branching (for example Neon, Supabase or PlanetScale), each CI job makes its own branch of the test database, migrates it to the head, runs, and deletes it; copies left by cancelled runs are pruned by age, and only branches with the CI prefix are ever deleted. Each job then has its own data and sign-in, so jobs from every PR run at the same time with no lock. Where branching is unavailable, use a disposable database on the runner or per-run data (step 7), and keep a lock only for what is truly shared. A reference implementation: Loopcraft's `scripts/ci-neon-branch.mjs` and `ui-browser.yml`.
- **One account per concurrent copy, not per test.** Parallel sign-ins to one account are often rate limited, so give each parallel worker or job its own account, seeded by the target's `seed` with the data its specs need. An account per test (hundreds) doesn't help: each needs seeding and a sign-in, jobs are bounded by the runner's CPU and the app instance they share, and every job pays install and build. The floor is the slowest spec file plus setup, so the useful number of jobs is roughly the total minutes divided by the slowest file's.
- **Small, known data.** Seed what each run needs and clean it up (step 7). Accumulated data slows tests twice over: pages render more, and full-page checks such as accessibility scans walk every element. The same slowdown hits real users with many records, so raise it as a product objective (paging, limits) and test scale deliberately in one journey, instead of by accident in all of them.
- **Fewer duplicate runs, not fewer checks.** Run layout, accessibility and responsive checks at every viewport. Journeys whose logic doesn't depend on the viewport can run at one, when the owner agrees. Use recorded coverage to find specs that execute the same code with the same assertions before removing any.
- **Scripted tests don't see the screen.** They check structure and behavior. Add screenshot comparisons (for example Playwright `toHaveScreenshot`) for screens whose content is stable, such as public pages, with baselines generated on the CI runner. With fuller per-PR checks, every change to screens users see also gets the verifier's reviewed screenshots ([verification](verification.md)); under the default minimum gates only risky features do, and the whole-suite run checks the rest.

## Keep the map current as the product changes

- **Every PR.** `ci` fails when a tracked file matches no feature, or a feature matches no file. A change to a feature's files always runs that feature's own suites, whatever coverage says, so UI changes keep their journeys when journeys run per PR (`"pr_journeys": true`); under the default minimum gates they keep their static suites and the whole-suite run covers the journeys. So a new area or a deleted one is mapped in the same PR that creates it. A mapping change is a gate change, so the independent verifier reviews it: the new paths, suites and level must fit what the code does.
- **Timings.** `ci` reports when a suite ran over 1.5 times its recorded minutes; update `minutes` then.
- **Whole-suite runs.** When `full_suite` calls for one, `ci --all` runs every suite, catching anything coverage could not see, and refreshes the recorded coverage, so journey selection follows the code as it changes without anyone editing the map. A failure there becomes a fix objective.
- **Larger product changes.** After a redesign, a new product area or a reorganised codebase, rerun steps 1 to 9 for the affected areas and rerun `smoke`. Re-running setup does this.
