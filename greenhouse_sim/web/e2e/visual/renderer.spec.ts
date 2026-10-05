import { expect, type Page, test } from "@playwright/test";

import { DEFAULT_QA_SEED, QA_RENDERER_PATH, QA_SELECTED_ID } from "../../src/qa/qaPage.ts";

const BASELINE = `renderer-seed-${DEFAULT_QA_SEED}.png`;
// Any other seed grows every plant to another height: a deliberate change.
const CHANGED_SEED = DEFAULT_QA_SEED + 1;

test.skip(process.platform !== "linux", "the baselines are drawn on Linux, in CI's container");

async function openQaPage(page: Page, seed: number): Promise<void> {
  await page.goto(`${QA_RENDERER_PATH}?seed=${seed}`);
  await expect(page.getByTestId("qa-caption")).toHaveText(`Renderer QA, seed ${seed}`);
  await expect(page.getByTestId("debug-label")).toHaveText(QA_SELECTED_ID);
}

test("the renderer's QA scene matches its baseline", async ({ page }) => {
  await openQaPage(page, DEFAULT_QA_SEED);

  await expect(page).toHaveScreenshot(BASELINE);
});

test("a changed scene differs from the baseline, and the restored scene matches", async ({
  page,
}, testInfo) => {
  const updating = ["all", "changed"].includes(testInfo.config.updateSnapshots);
  test.skip(updating, "this test only reads the baseline, so it must not rewrite it");

  await openQaPage(page, CHANGED_SEED);
  const matched = await expect(page)
    .toHaveScreenshot(BASELINE)
    .then(
      () => true,
      () => false,
    );
  expect(matched, "the changed scene should not match the baseline").toBe(false);

  await openQaPage(page, DEFAULT_QA_SEED);
  await expect(page).toHaveScreenshot(BASELINE);
});
