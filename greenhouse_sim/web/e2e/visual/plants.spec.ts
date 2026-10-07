import { expect, test } from "@playwright/test";

import { QA_PLANTS_PATH } from "../../src/qa/plantViews.ts";

test.skip(process.platform !== "linux", "the baselines are drawn on Linux, in CI's container");

test("the plant lab's first plant on days 0, 30, 60 and 90 matches its baseline", async ({
  page,
}) => {
  await page.goto(QA_PLANTS_PATH);
  await expect(page.getByTestId("qa-caption")).toHaveText("Plant QA, days 0, 30, 60, 90");

  await expect(page).toHaveScreenshot("plants-time-lapse.png");
});
