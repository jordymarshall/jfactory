# Goal tests: Playwright specs from job goals

A goal test proves one standing goal from a job document (`outcomes/<job>.md`). It is an ordinary browser test, such as a Playwright spec, that an agent writes from the goal's words. CI runs it like every other spec: free, exact and repeatable, with the project's existing test account. Setup writes goal tests for every adopting repository that has screens.

The spec is the replay. An agent reads the goal once, drives the app, and commits exact steps and exact checks. Later runs repeat the committed steps and call no model. When the screens change, an agent updates the spec in the same PR, as for any test.

Agents write these specs in their own sessions, on the owner's subscriptions. CI needs no model and no API key.

## What setup does

1. **Choose the key goals.** For each job document, start with the most important journeys: the ones the outcomes in `outcomes/README.md` depend on. Take 3 to 5 goals per job first, chosen from rows that describe a result a user sees or does in the app.
2. **Write one spec per goal.** Put it in the project's end-to-end folder, one file per job: `e2e/goals/<job>.spec.ts`, where `<job>` is the job document's file name. Name each test after its goal, in the goal's words. Start from [templates/goal-test.spec.ts](../templates/goal-test.spec.ts). Reuse the project's sign-in fixture and helpers.
3. **Run each spec against the real app.** Watch it pass. Then break the behavior it checks, or read the assertion against the goal, to confirm the test can fail for the right reason.
4. **Link each test from its goal.** In the job document's "How it's proven" cell, name the file and the test title, for example `` `e2e/goals/plan-a-brief.spec.ts` "a free brief saves without invented references" ``. Say what the test does not prove, as for any other proof.
5. **Map the specs as a suite.** Add a goal suite to `.jfactory/verification.json` ([below](#map-goal-suites)).

`setup_check.py` warns when the job documents of features with screens link no goal test (a spec under a `goals/` folder) in their "How it's proven" column.

### Which goals get a goal test

| Goal kind | Proof |
| --- | --- |
| A result the user sees or does in the app ("a saved brief survives reload") | A goal test |
| A quality ("the empty state explains what to do next") | The job document's judgment rubric, with reviewed screenshots and the verifier's [UX explore](../skills/jfactory-ux/references/bug-bash.md#explore-for-ux-review) |
| A measure from production ("half of new users launch a test") | The measure. A goal test cannot prove it |
| A rule inside one function | A unit test |

A goal that an older spec already proves needs no second test. Link the existing test instead.

## Write a goal test

Each test follows the same shape:

1. Start where the user starts: open the page, signed in when the job needs it.
2. Do what the goal says, with the controls a user uses. Find them by role and visible name, not by CSS classes.
3. Check the result with an exact assertion, for example that the saved brief shows its name.
4. Check persistence where the goal needs it: reload, or open the record again, and assert the exact value.

Follow these rules:

- **One goal per test.** The test title is the goal, in the job document's words.
- **Judge meaning, not wording.** Assert the value the goal is about, not a whole paragraph of copy.
- **Make generated data unique.** Put a timestamp or the run's ID in every name a test creates, so runs never collide.
- **Clean up what the test creates.** Delete or archive the test's records in `afterEach`, or through the target's `cleanup`. Never let each run add records to a shared account for ever ([mapping, step 7](mapping.md#7-define-where-the-app-runs-and-prove-it-starts)).
- **Keep each test independent.** Each test creates the data it needs.
- **Never run goal tests against production.** They create and change records. Use a local app, a PR preview or staging.

## When the screens change

A goal test fails when a control it uses is renamed or moved, even when the goal still holds. That is the cost of exact steps.

1. Read the failure and the screenshot. Decide whether the product broke the goal or only changed its steps.
2. If the product broke the goal, the change fails verification. Fix the product, not the test.
3. If only the steps changed on purpose, update the spec in the same PR. Keep the goal and the assertions on the result. Change only the steps.

An agent may rewrite a spec from its goal when the screens changed a lot. The independent verifier then checks that the new spec still asserts the goal ([verification contract](verification.md#change-aware-verification-and-the-merge-gate): a change to tests always gets an independent verdict).

## Map goal suites

Map each job's goal spec as a journey suite ([guided mapping](mapping.md#6-define-suites-that-can-run-alone)):

```json
"goals-briefs": {"run": "cd app && E2E_BASE_URL=$BASE_URL npx playwright test e2e/goals/plan-a-brief.spec.ts", "minutes": 3, "target": "local"}
```

1. Give the suite a `target`, because it needs the running app, and measured `minutes`.
2. Add it to the `suites` of the feature whose job document it proves.
3. Add the spec file to that feature's `paths` as well, so a change to the test plans its suite.

`verify_plan.py plan` then selects the goal suite only when that feature's code changed, as for every suite. A goal suite never goes in `always_suites` or `static_suites`: `audit` fails on a suite with a `target` there.

## How the verifier uses goal tests

A goal test is evidence for its goal at the scopes it reaches: usually `application`, against the identified target. The verifier reads what each test asserts and compares it with the goal's words. A test that clicks through the journey but never checks the result proves nothing. The verifier also runs a [UX explore](../skills/jfactory-ux/references/bug-bash.md#explore-for-ux-review) of the changed journey, because a spec checks the result, not whether the steps felt clear.

## Optional: self-healing agent steps with e2e

Some repositories want steps that heal themselves when the screens change. The open-source tool [e2e](https://github.com/tester-army/e2e) (npm packages `e2e` and `@e2e-dev/web`) runs plain-language steps with a model, and replays recorded steps from a committed cache. Use it only when the owner agrees to pay for model calls in CI.

- **It needs a model API key in CI**, for example `AI_GATEWAY_API_KEY` for the Vercel AI Gateway. A Claude subscription does not work with e2e. Subscriptions are for people and agent sessions, not for CI.
- **Commit the replay cache.** `e2e init` ignores `.e2e/cache/`. Remove that line and commit the folder, so CI replays verified steps without a model call. CI reads the cache only; a stale step calls the model on every run until someone re-records it.
- **Keep model judgments off the gate.** `agent.assert`, `agent.waitFor` and `agent.extract` call the model on every run. Put a suite that uses them under `"live_model": true` ([journeys a model drives](mapping.md#journeys-a-model-drives)).
- **Without the key, skip the suite with a visible notice.** Never report it as passed.

The optional templates [templates/optional-e2e.config.ts](../templates/optional-e2e.config.ts) and [templates/optional-goal-test.e2e.ts](../templates/optional-goal-test.e2e.ts) show the shape. The e2e documentation ships offline in `node_modules/e2e/docs`.
