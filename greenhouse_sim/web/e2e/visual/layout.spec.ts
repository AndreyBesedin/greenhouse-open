import { expect, test } from "@playwright/test";

import { QA_LAYOUT_PATH, QA_LAYOUT_VIEWS } from "../../src/qa/layoutViews.ts";

test.skip(process.platform !== "linux", "the baselines are drawn on Linux, in CI's container");

for (const view of QA_LAYOUT_VIEWS) {
  test(`the QA layout's ${view} view matches its baseline`, async ({ page }) => {
    await page.goto(`${QA_LAYOUT_PATH}?view=${view}`);
    await expect(page.getByTestId("qa-caption")).toHaveText(`Layout QA, ${view} view`);

    await expect(page).toHaveScreenshot(`layout-${view}.png`);
  });
}
