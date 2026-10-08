import { expect, test } from "@playwright/test";

import { selectAt } from "./view";

// The example scene's greenhouse (the climate box) is 12 m long and 6.4 m
// wide, of one span and three bays, its eaves at 4 m and its ridge at 4.8 m,
// with its floor corner at the world's origin.
// Inside the greenhouse, over the floor between its right side wall and its
// first row, clear of the plants and of the path across its front.
const INSIDE_OVER_THE_FLOOR = { x: 3, y: 0.6, z: 0.6 };
// Low on the right side wall, which the front view looks at from floor level:
// the click rises through it over the young plants, between their gutters
// and their wires, past the glass on the far side, to the sky.
const SIDE_WALL = { x: 3, y: 0, z: 1.2 };

test("the greenhouse is measured and labelled, and its glass yields to what it encloses", async ({
  page,
}) => {
  await page.goto("/?scene=example");
  await expect(page.getByTestId("scene-status")).toContainText("121 entities");

  await page.getByLabel("Dimensions and axis labels").check();
  await expect(page.getByTestId("debug-label")).toHaveText([
    "x",
    "y",
    "z",
    "length 12.00 m",
    "width 6.40 m",
    "height 4.80 m",
  ]);
  await page.getByLabel("Dimensions and axis labels").uncheck();
  await expect(page.getByTestId("debug-label")).toHaveCount(0);

  // A click through the glass reaches the floor inside.
  await selectAt(page, INSIDE_OVER_THE_FLOOR, "climate_box_floor");

  // With nothing solid behind it, the glass itself is picked.
  await page.getByRole("button", { name: "Front" }).click();
  await selectAt(page, SIDE_WALL, "climate_box_side_wall_right", "front");
  await expect(page.getByTestId("selected-shape")).toHaveText("plane, 12.00 × 4.00 m");
  await expect(page.getByTestId("selected-position")).toHaveText("x 6.00, y 0.00, z 2.00");
});

test("the surface categories colour the envelope by what each part is", async ({ page }) => {
  await page.goto("/?scene=example");
  await expect(page.getByTestId("scene-status")).toContainText("121 entities");

  await page.getByRole("checkbox", { name: "Categories" }).check();
  await expect(page.getByTestId("category")).toHaveText([
    "floor",
    "wall",
    "roof",
    "vent",
    "door",
    "gutter",
    "frame",
  ]);
  await page.getByRole("checkbox", { name: "Categories" }).uncheck();
  await expect(page.getByTestId("category")).toHaveCount(0);
});
