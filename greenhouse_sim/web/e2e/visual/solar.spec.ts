import { expect, test } from "@playwright/test";

import { QA_SOLAR_PATH, QA_SOLAR_VIEWS } from "../../src/qa/solarPage.ts";

test.skip(process.platform !== "linux", "the baselines are drawn on Linux, in CI's container");

for (const view of QA_SOLAR_VIEWS) {
  test(`the solar QA case's ${view} view matches its baseline`, async ({ page }) => {
    await page.goto(`${QA_SOLAR_PATH}?view=${view}`);
    await expect(page.getByTestId("qa-caption")).toContainText(`Solar QA, ${view} view`);

    await expect(page).toHaveScreenshot(`solar-${view}.png`);
  });
}
