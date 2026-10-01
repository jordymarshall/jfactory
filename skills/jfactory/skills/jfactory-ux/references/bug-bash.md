# Bug bash: explore in parallel, then prove every finding

A bug bash sends several explorers through the running app at once, one charter each. A verification pass then proves every claimed bug with a repro test that fails for the reason reported. Explorers are models, and a model's finding is a claim, not a bug. Report confirmed bugs only, each with its failing test.

Run one when the owner asks to bug bash, QA or hunt for bugs; before releasing a large change to screens users see; or after a redesign, when the scripted journeys no longer cover how people actually move through the app. It is not part of every PR: the independent verifier drives the changed journeys, while a bug bash looks for what nobody thought to check.

The bundled helper keeps the bug bash's records in one study, and its commands take the study's folder:

```sh
UX="python3 <bundle>/skills/jfactory-ux/scripts/study.py"
STUDY="$($UX init bugbash-<date> --url <app> --objective "<area and why>")"
```

The procedure is adapted from the bug-bash guide in [tester-army/e2e](https://github.com/tester-army/e2e) (Apache-2.0).

## 1. Prepare

- **An app that can serve several explorers.** Prefer a production build: a dev server that compiles a route on its first visit looks like a dead link to an explorer. Start it once and point every explorer at it, or give each explorer its own port. When the app's start command also brings up its own database, start that stack once yourself. Otherwise the first explorer to finish tears it down under the others.
- **One disposable account per charter.** Seed it with the project's own fixtures or the target's `seed` command. Explorers that share an account report each other's edits as bugs.
- **Context for every explorer.** Tell each explorer what the local stack cannot do (no email provider, no payment keys) and what it must never click (paid runs, real accounts, invitations). Tell it which data is seed data. Give it the blind spots in [step 5](#5-triage-before-writing-any-test) as "not bugs" so they don't fill the findings.
- **A shared, deployed site is read-only.** No sign-ups, submissions or injection-shaped input, and no request loops. A firewall block is the firewall working, not a finding.
- **Budgets.** Set a step and time limit per charter and a total cost cap, and write them in the objective.

## 2. Plan charters

A charter is one sentence: the start route, one area and one posture. It names the account when it needs one. Read the routes, navigation and forms first. For a branch, read `git diff --stat` against the base and aim the charters at what changed.

| Posture | Charter shape |
| --- | --- |
| `first-time` | Starting at /signup, sign up and finish onboarding like a first-time user; report anything confusing, broken or inconsistent |
| `numbers` | Starting at /cart, change quantities and apply a coupon; check every price, total and label against the rest of the page |
| `edge-input` | Starting at /settings/profile, submit each field empty, 300 characters long, with emoji and with leading spaces; report validation that is missing or wrong |
| `state` | Starting at /projects, create, rename and delete a project, reloading and going back after each; report state that is lost or stale |
| `errors` | Starting at /login, try a wrong password, an unknown account and a locked account; report errors that are missing, misleading or leak detail |

Plan five to ten charters. Overlap is fine; duplicates are merged in step 4. One charter covers one area: a charter that spans the whole app runs out of steps after skimming everything. An `edge-input` charter lists its exact inputs, or the explorer spends its budget before judging any of them. Record each one:

```sh
$UX charter "$STUDY" cart --posture numbers "Starting at /cart, change quantities and apply a coupon; check every price, total and label against the rest of the page"
```

**Give each posture its own stance.** A generic explorer walks past a total that contradicts the same total on another page. Brief a **skeptic** to distrust every number, date, count and claim on screen and cross-check each against everywhere else it appears. Brief a **fuzzer** to run its charter's input list at every field before anything else, judging each result before the next input, and never to take the happy path.

## 3. Fan out

Run up to four explorers at a time. Each one gets its charter, account, context and stance, and works in its own browser session and output folder. Any capable explorer works:

- **Subagents.** Give each subagent a browser session of its own (`study.py browser` with a separate study, or the host's browser tool).
- **The project's agentic test tool.** For example, `npx e2e explore "<charter>" --output .e2e/bugbash/<slug> --reporter list,markdown --video` from [e2e](https://github.com/tester-army/e2e) writes each finding with its expected and actual result, steps and a screenshot. Ignore its output folder in git.

For every defect it sees, the explorer reports a title, `issue` or `warning`, a severity from 1 (trivial) to 5 (critical), where it happened, expected against actual, the steps that reach it, and a screenshot or video. Record each one as a claim, with its evidence copied into the study's `artifacts/`:

```sh
$UX claim "$STUDY" --charter cart --severity 4 --title "Coupon applied twice" --where /cart --expected "Total \$9.00 for one item with SAVE10" --actual "Total \$8.10" --step "Open /cart" --step "Apply SAVE10" --evidence artifacts/cart-1.png
```

## 4. Merge

Findings that describe one defect (same place, same broken behavior) are one finding. Keep the clearest reproduction and note every charter that hit it. Reject the others as `duplicate`, naming the finding they repeat. Keep warnings separate unless the owner asked for polish.

## 5. Triage before writing any test

Read the source and sort every claim. Settle the explorer-artifact bucket first; it is the most common.

| Bucket | Sign | Outcome |
| --- | --- | --- |
| `artifact` | A "dead" link that opens in a new tab, a sentence the screenshot shows whole but the accessibility text splits around a link, a "Loading more" item nothing scrolled to, an image that loads lazily | Reject, naming the check that settled it. A new-tab link whose destination never opens stays a candidate |
| `environment` | Fails only for a key, service or limit the local stack lacks | Reject, naming the variable or service. Note separately when the app handles that failure badly in a way production users would see, such as showing the raw error |
| `design` | The code, its tests or its copy say the behavior is intended | Reject, citing where |
| `fixture` | The seed data lacks a field real records always have | Reject, naming the field |
| Candidate | None of the above | Verify it (step 6) |

```sh
$UX reject "$STUDY" 3 --bucket artifact --reason "The Docs link opens in a new tab; the destination loads when clicked with popups allowed"
```

## 6. Verify each candidate with a repro test

Use separate verifiers, one per area with three to five candidates each, so the agent that explored does not grade its own claims. Each verifier:

1. Reads the claim's actual result against its screenshot or video. A claim the evidence contradicts is rejected here.
2. Writes a repro test in the project's own test framework. It follows the reproduction and asserts the **expected** behavior, so it fails today and passes once the bug is fixed. Prefer exact interactions and assertions with exact values; get locators from the live app rather than guessing them.
3. Confirms it. `confirm` runs the test and accepts the finding only when the test fails with output matching the assertion that encodes the bug:

   ```sh
   $UX confirm "$STUDY" 1 --repro tests/bugbash/coupon.spec.ts --expect-failure 'Expected.*\$9\.00' -- npx playwright test tests/bugbash/coupon.spec.ts
   ```

   A passing test means the bug did not reproduce: reject the finding as `not-reproduced`, and keep the test only as an ordinary regression test if it is worth having. Any other failure, such as a missing locator, a timeout or a setup error, means the test is wrong: fix it and confirm again.

## 7. Report

`$UX bugs "$STUDY"` writes `bugs.md` and exits 1 while any claim is still unverified. It lists confirmed bugs first, most severe first, each with expected against actual, steps, repro test, log and evidence. Then the unverified claims, the rejected ones grouped by bucket, the warnings and the charters run. Add the environment risks that production users could hit, marked unverified, the total cost, and the areas no charter reached.

The repro tests fail until their bugs are fixed, so keep them out of the gating suite: leave them uncommitted, or tag them and exclude the tag from CI. Offer to fix each bug as its own objective. The repro test becomes that fix's regression criterion, proven with [`evidence.py contrast`](../../../references/verification.md#prove-a-fix-fails-before-it-and-passes-after-it): it fails on the base and passes at the head. Remove its bug-bash tag once it passes.

## Rules

- Never report an unverified finding as a bug. "The explorer reported" is not "confirmed".
- Leave the project as you found it. The bug-bash config, seed data and repro tests stay out of the base branch until the owner decides, and stop any stack you started.
- Screenshots and videos can show secrets and customer data. Check them before sharing, and keep raw captures in the private study folder.
