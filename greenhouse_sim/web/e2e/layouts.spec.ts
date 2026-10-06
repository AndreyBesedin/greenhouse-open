import { expect, test } from "@playwright/test";

import { selectAt } from "./view";

// gh_001's layouts are files: its default one grows its rows in gutters, and
// benches.json puts the same rows on benches, their tops at 0.8 m. On the
// first bench, beside the plants, nearer the default camera.
const ON_THE_FIRST_BENCH = { x: 3.0, y: 1.9, z: 0.8 };

test("a scenario's layouts are switched in the viewer, without code changes", async ({ page }) => {
  await page.goto("/?scenario=gh_001");
  const status = page.getByTestId("scene-status");
  await expect(status).toContainText("gh_001, day 0, 165 entities");
  const picker = page.getByRole("combobox", { name: "Layout of gh_001" });
  await expect(picker).toHaveValue("default");

  await picker.selectOption("benches");
  await expect(status).toHaveText(
    "Showing the scenario gh_001 with its benches layout, before day one: gh_001, day 0, 155 entities.",
  );
  await expect(page).toHaveURL(/\?scenario=gh_001&layout=benches$/);
  await selectAt(page, ON_THE_FIRST_BENCH, "gh_001_row_1_support_1");
  await expect(page.getByTestId("selected-type")).toHaveText("bench");
  await expect(page.getByTestId("selected-dimensions")).toHaveText(
    "length 5.00 m, width 1.20 m, height 0.05 m",
  );

  // The address keeps the layout.
  await page.reload();
  await expect(status).toContainText("benches layout");
  await expect(picker).toHaveValue("benches");

  await picker.selectOption("default");
  await expect(status).toContainText("gh_001, day 0, 165 entities");
  await expect(page).toHaveURL(/\?scenario=gh_001$/);
});
