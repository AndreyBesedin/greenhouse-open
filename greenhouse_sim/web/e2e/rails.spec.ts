import { expect, test } from "@playwright/test";

import { selectAt } from "./view";

// The compartment's first pipe rail runs between its first two rows, along
// y = 3.2 m, its tubes 0.55 m apart with their axes 10 cm up; four heating
// pipes run along its right side wall at y = 0.25 m, the top one 0.75 m up.
// From the side the gutters hide the rails, so a rail is picked from above,
// on top; from above the roof's gutter hides the heating pipes, so a pipe is
// picked from the front right, through the side wall's glass.
const TUBE_RADIUS_M = 0.0255;
const RAIL_TUBE_TOP = { x: 3.1, y: 3.2 + 0.275, z: 0.1 + TUBE_RADIUS_M };
const TOP_HEATING_PIPE = { x: 3.0, y: 0.25 - TUBE_RADIUS_M / 2, z: 0.75 + TUBE_RADIUS_M / 2 };

test("the compartment's rails and heating pipes are picked as what they are", async ({ page }) => {
  await page.goto("/?scenario=tomato_compartment");
  await expect(page.getByTestId("scene-status")).toContainText(
    "tomato_compartment, day 0, 896 entities",
  );
  await page.getByRole("button", { name: "Top" }).click();
  const inspector = page.getByRole("region", { name: "Inspector" });
  const shape = page.getByTestId("selected-shape");

  await selectAt(page, RAIL_TUBE_TOP, "tomato_compartment_rail_1_1_left", "top");
  await expect(inspector.getByText("RAIL", { exact: true })).toBeVisible();
  // Along its 20 m rows.
  await expect(shape).toHaveText("cylinder, radius 0.03 m, height 20.00 m");
  await expect(page.getByTestId("property-obstructs_movement")).toHaveText("true");
  await expect(page.getByTestId("property-obstructs_airflow")).toHaveText("false");

  await page.getByRole("button", { name: "Isometric" }).click();
  await selectAt(page, TOP_HEATING_PIPE, "tomato_compartment_heating_pipes_right_4");
  await expect(inspector.getByText("PIPE", { exact: true })).toBeVisible();
  await expect(shape).toHaveText("cylinder, radius 0.03 m, height 21.80 m");
  await expect(page.getByTestId("selected-material")).toHaveText("steel");
});
