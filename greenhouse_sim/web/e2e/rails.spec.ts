import { expect, test } from "@playwright/test";

import { selectAt } from "./view";

// gh_001's first pipe rail runs between its first two rows, along y = 3.2 m,
// its tubes 0.55 m apart with their axes 10 cm up; four heating pipes run
// along its right side wall at y = 0.25 m, the top one 0.75 m up. From the
// side the gutters hide the rails, so both are picked from above, on top.
const TUBE_RADIUS_M = 0.0255;
const RAIL_TUBE_TOP = { x: 3.1, y: 3.2 + 0.275, z: 0.1 + TUBE_RADIUS_M };
const TOP_HEATING_PIPE = { x: 3.0, y: 0.25, z: 0.75 + TUBE_RADIUS_M };

test("gh_001's rails and heating pipes are picked as what they are", async ({ page }) => {
  await page.goto("/?scenario=gh_001");
  await expect(page.getByTestId("scene-status")).toContainText("gh_001, day 0, 165 entities");
  await page.getByRole("button", { name: "Top" }).click();
  const inspector = page.getByRole("region", { name: "Inspector" });
  const shape = page.getByTestId("selected-shape");

  await selectAt(page, RAIL_TUBE_TOP, "gh_001_rail_1_1_left", "top");
  await expect(inspector.getByText("RAIL", { exact: true })).toBeVisible();
  await expect(shape).toHaveText("cylinder, radius 0.03 m, height 5.00 m");
  await expect(page.getByTestId("property-obstructs_movement")).toHaveText("true");
  await expect(page.getByTestId("property-obstructs_airflow")).toHaveText("false");

  await selectAt(page, TOP_HEATING_PIPE, "gh_001_heating_pipes_right_4", "top");
  await expect(inspector.getByText("PIPE", { exact: true })).toBeVisible();
  await expect(shape).toHaveText("cylinder, radius 0.03 m, height 6.50 m");
  await expect(page.getByTestId("selected-material")).toHaveText("steel");
});
