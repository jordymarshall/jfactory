// OPTIONAL add-on, not the default (references/goal-tests.md#optional-self-healing-agent-steps-with-e2e). The default
// goal test is a Playwright spec (templates/goal-test.spec.ts). Copy to e2e/goals/<job>.e2e.ts when the repo uses e2e.
import { expect, test, unique } from 'e2e';

// REPLACE with the goal's words from outcomes/<job>.md.
test('REPLACE: a saved item survives reload with its exact name', { session: 'member' }, async ({ app, agent, screen }) => {
  // unique() lets the replay cache repeat this step with a new value on every run.
  const name = `Goal test ${Date.now()}`;

  // 1. Start where the user starts.
  await app.open('/REPLACE');

  // 2. One goal, in the words on the screen. The model chooses the clicks; the cache replays them later.
  await agent.act('create an item named {name} and save it', { params: { name: unique(name) } });

  // 3. The proof: an exact check. It also confirms the step, so e2e records it for replay.
  await expect(screen.getByRole('heading', { name })).toBeVisible();

  // 4. Persistence, when the goal needs it: open the page again and check the exact value.
  await app.open('/REPLACE');
  await expect(screen.getByText(name)).toBeVisible();

  // Optional: a judgment no locator can make. It calls the model on EVERY run, even with a full cache,
  // so use it only in a suite marked "live_model": true.
  // await agent.assert('the item page says when the item was saved');
});
