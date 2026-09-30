# Objective: <one sentence a stranger could act on>

Keep this in the project's task location (named in the setup record), for example a GitHub issue. Update it as the work progresses; do not start a new one each turn.

## Outcome
Customer and experience outcome. Name the business outcome in `outcomes/README.md` and the job document(s) in `outcomes/` this work serves.
- **Owner decisions:** <what the owner decided, with the source>
- **Agent assumptions:** <what the agent inferred and has not confirmed>
- **Open questions:** <consequential choices still unsettled>

## Route
Loops this objective uses, and why. See the routing table in `references/methodology.md`.
- **Product:** <yes or skip, and why>
- **UX:** <review, research or skip, and why>
- **Engineering:** yes
- **Workflow:** <only if a repeated correction is involved>

## Scope
- **In scope:** <paths or behavior>
- **Out of scope:** <non-goals>
- **Depends on:** <other PRs or units>

## Acceptance criteria

These are the criteria for this piece of work. Each one adds, changes or relies on a standing goal in a job document; say which. When the work adds or changes a standing goal, update that job document in the same PR, with its proof.

| ID | Criterion (starting state, action, expected result) | Job goal it adds, changes or relies on | Required scopes | How it is proven |
| --- | --- | --- | --- | --- |
| save | A signed-in user saves an item and sees it after reload and in a new session | `outcomes/save-items.md`: "A saved item survives reload" (adds) | application | `npm run test:e2e -- save.spec.ts` against the PR preview, plus a storage readback |
| clear | Saving an item is quick and obvious for a first-time user | `outcomes/save-items.md` rubric (relies on) | judgment | Rubric below, scored by the independent verifier from the walkthrough video and screenshots |

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
- **Merge and release policy:** <what merging does; production needs an owner request and follows the `release` procedure in .jfactory/coordination.json>

## Status
| Criterion | Result | Evidence and commit |
| --- | --- | --- |

- **Blockers:** <what is stuck>
- **Next action:** <what a resumed session does first>
