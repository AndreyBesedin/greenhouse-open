import { expect, test } from "@playwright/test";

import { QA_GREENHOUSE_PATH, QA_GREENHOUSE_VIEWS } from "../../src/qa/greenhouseViews.ts";

test.skip(process.platform !== "linux", "the baselines are drawn on Linux, in CI's container");

for (const view of QA_GREENHOUSE_VIEWS) {
  test(`the QA greenhouse's ${view} view matches its baseline`, async ({ page }) => {
    await page.goto(`${QA_GREENHOUSE_PATH}?view=${view}`);
    await expect(page.getByTestId("qa-caption")).toHaveText(`Greenhouse QA, ${view} view`);

    await expect(page).toHaveScreenshot(`greenhouse-${view}.png`);
  });
}
