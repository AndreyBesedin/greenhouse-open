import { expect, test } from "@playwright/test";

import { selectAt } from "./view";

// The compartment's layouts are files: its default one grows its rows in
// gutters, and propagation.json raises the same rows on benches, their tops
// at 0.8 m. On the first bench, beside the plants, nearer the default camera.
const ON_THE_FIRST_BENCH = { x: 3.0, y: 1.9, z: 0.8 };

test("a scenario's layouts are switched in the viewer, without code changes", async ({ page }) => {
  await page.goto("/?scenario=tomato_compartment");
  const status = page.getByTestId("scene-status");
  await expect(status).toContainText("tomato_compartment, day 0, 896 entities");
  const picker = page.getByRole("combobox", { name: "Layout of tomato_compartment" });
  await expect(picker).toHaveValue("default");

  await picker.selectOption("propagation");
  await expect(status).toHaveText(
    "Showing the scenario tomato_compartment with its propagation layout, before day one: tomato_compartment, day 0, 898 entities.",
  );
  await expect(page).toHaveURL(/\?scenario=tomato_compartment&layout=propagation$/);
  await selectAt(page, ON_THE_FIRST_BENCH, "tomato_compartment_row_1_support_1");
  await expect(page.getByTestId("selected-type")).toHaveText("bench");
  await expect(page.getByTestId("selected-dimensions")).toHaveText(
    "length 20.00 m, width 1.20 m, height 0.05 m",
  );

  // The address keeps the layout.
  await page.reload();
  await expect(status).toContainText("propagation layout");
  await expect(picker).toHaveValue("propagation");

  await picker.selectOption("default");
  await expect(status).toContainText("tomato_compartment, day 0, 896 entities");
  await expect(page).toHaveURL(/\?scenario=tomato_compartment$/);
});
