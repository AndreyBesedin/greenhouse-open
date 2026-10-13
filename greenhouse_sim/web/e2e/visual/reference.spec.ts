import { expect, test } from "@playwright/test";

import { QA_REFERENCE_PATH, QA_REFERENCE_VIEWS } from "../../src/qa/referencePage.ts";

test.skip(process.platform !== "linux", "the baselines are drawn on Linux, in CI's container");

// The reference greenhouse's views draw its whole crop on day 80, some
// thirteen thousand organs, in software: they take longer to settle than
// the other QA pages.
const REFERENCE_VIEW_TIMEOUT_MS = 90_000;

for (const view of QA_REFERENCE_VIEWS) {
  test(`the reference greenhouse's ${view} view matches its baseline`, async ({ page }) => {
    test.setTimeout(REFERENCE_VIEW_TIMEOUT_MS);
    await page.goto(`${QA_REFERENCE_PATH}?view=${view}`);
    await expect(page.getByTestId("qa-caption")).toContainText(
      `Reference greenhouse, ${view} view`,
      { timeout: REFERENCE_VIEW_TIMEOUT_MS / 2 },
    );
    // Its state probes are said on it, and drawn with it.
    await expect(page.getByTestId("qa-probes")).toContainText("house air");

    await expect(page).toHaveScreenshot(`reference-${view}.png`);
  });
}
