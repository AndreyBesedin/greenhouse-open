import { expect, test } from "@playwright/test";

import { QA_AIRFLOW_PATH, QA_AIRFLOW_VIEWS } from "../../src/qa/airflowViews.ts";

test.skip(process.platform !== "linux", "the baselines are drawn on Linux, in CI's container");

for (const view of QA_AIRFLOW_VIEWS) {
  test(`the airflow QA case's ${view} view matches its baseline`, async ({ page }) => {
    await page.goto(`${QA_AIRFLOW_PATH}?view=${view}`);
    await expect(page.getByTestId("qa-caption")).toHaveText(`Airflow QA, ${view} view`);

    await expect(page).toHaveScreenshot(`airflow-${view}.png`);
  });
}
