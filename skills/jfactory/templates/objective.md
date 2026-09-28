# Objective: <one sentence a stranger could act on>

Keep this in the project's task location (named in the setup record), for example a GitHub issue. Update it as the work progresses; do not start a new one each turn.

## Outcome
Customer and experience outcome.
- **Owner decisions:** <what the owner decided, with the source>
- **Agent assumptions:** <what the agent inferred and has not confirmed>
- **Open questions:** <consequential choices still unsettled>

## Scope
- **In scope:** <paths or behavior>
- **Out of scope:** <non-goals>
- **Depends on:** <other PRs or units>

## Acceptance criteria

| ID | Criterion (starting state, action, expected result) | Required scopes | How it is proven |
| --- | --- | --- | --- |
| save | A signed-in user saves an item and sees it after reload and in a new session | application | `npm run test:e2e -- save.spec.ts` against the PR preview, plus a storage readback |
| clear | Saving an item is quick and obvious for a first-time user | judgment | Rubric below, scored by the independent verifier from the walkthrough video and screenshots |

For a `judgment` criterion, write the rubric before building. Give each point something the judge can observe, and set a pass mark:

- **Rubric for `clear`:** passes when all of these hold.
  1. The save control is visible without scrolling on a 390x844 viewport.
  2. Saving takes at most two actions.
  3. The confirmation names the saved item.
  4. An error state explains how to retry.

## Execution
- **Target:** <local, preview or staging>
- **Accounts and data:** <which, and who owns them>
- **Permitted side effects:** <what the agent may change>
- **Limits:** <cost or time caps>

## Review and stop
- **Checkpoint:** <when the owner reviews>
- **Stop conditions:** <when to stop, e.g. the criteria pass>
- **Merge and release policy:** <what merging does; production needs an owner request>

## Status
| Criterion | Result | Evidence and commit |
| --- | --- | --- |

- **Blockers:** <what is stuck>
- **Next action:** <what a resumed session does first>
