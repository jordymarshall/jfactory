// A goal test: one Playwright spec per key goal of a job document (references/goal-tests.md).
// Copy it to e2e/goals/<job>.spec.ts, name each test after its goal, and link the test from the goal's
// "How it's proven" cell in outcomes/<job>.md. Replace every REPLACE.
import { expect, test } from '@playwright/test'; // REPLACE with the project's signed-in fixture, if it has one

test.afterEach(async () => {
  // REPLACE: delete or archive the records this test created, so a shared account does not grow.
});

// REPLACE with the goal's words from outcomes/<job>.md.
test('REPLACE: a saved item survives reload with its exact name', async ({ page }) => {
  // Unique per run, so runs never collide and clean-up can find this run's data.
  const name = `Goal test item ${Date.now()}`;

  // 1. Start where the user starts.
  await page.goto('/REPLACE');

  // 2. Do what the goal says, with the controls a user uses (role and visible name).
  await page.getByRole('button', { name: 'REPLACE: New item', exact: true }).click();
  await page.getByRole('textbox', { name: 'REPLACE: Name', exact: true }).fill(name);
  await page.getByRole('button', { name: 'REPLACE: Save', exact: true }).click();

  // 3. The proof: an exact check of the result the goal is about.
  await expect(page.getByRole('heading', { name, exact: true })).toBeVisible();

  // 4. Persistence, when the goal needs it: load the page again and check the exact value.
  await page.reload();
  await expect(page.getByText(name, { exact: true })).toBeVisible();
});
