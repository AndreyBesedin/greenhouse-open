import { expect, test } from "@playwright/test";

import { selectAt } from "./view";

// The example scene's greenhouse (gh_demo) is 4 m long and 6.4 m wide, of two
// spans and two bays, its eaves at 3 m and its ridges at 3.65 m, with its
// floor corner at the world's origin.
// Inside the greenhouse, over the floor and clear of the plants.
const INSIDE_OVER_THE_FLOOR = { x: 1, y: 1, z: 1 };
// Low on the back gable, which the side view looks at from floor level: the
// click rises through it over the plants, past glass, to the sky.
const BACK_GABLE = { x: 4, y: 1.5, z: 1.2 };

test("the greenhouse is measured and labelled, and its glass yields to what it encloses", async ({
  page,
}) => {
  await page.goto("/?scene=example");
  await expect(page.getByTestId("scene-status")).toContainText("45 entities");

  await page.getByLabel("Dimensions and axis labels").check();
  await expect(page.getByTestId("debug-label")).toHaveText([
    "x",
    "y",
    "z",
    "length 4.00 m",
    "width 6.40 m",
    "height 3.65 m",
  ]);
  await page.getByLabel("Dimensions and axis labels").uncheck();
  await expect(page.getByTestId("debug-label")).toHaveCount(0);

  // A click through the glass reaches the floor inside.
  await selectAt(page, INSIDE_OVER_THE_FLOOR, "gh_demo_floor");

  // With nothing solid behind it, the glass itself is picked.
  await page.getByRole("button", { name: "Side" }).click();
  await selectAt(page, BACK_GABLE, "gh_demo_end_wall_back", "side");
  // A gable of two spans: two peaks and the valley between them.
  await expect(page.getByTestId("selected-shape")).toHaveText("polygon, 7 corners");
  await expect(page.getByTestId("selected-position")).toHaveText("x 4.00, y 6.40, z 0.00");
});

test("the surface categories colour the envelope by what each part is", async ({ page }) => {
  await page.goto("/?scene=example");
  await expect(page.getByTestId("scene-status")).toContainText("45 entities");

  await page.getByRole("checkbox", { name: "Surface categories" }).check();
  await expect(page.getByTestId("category")).toHaveText([
    "floor",
    "wall",
    "roof",
    "vent",
    "door",
    "gutter",
    "frame",
  ]);
  await page.getByRole("checkbox", { name: "Surface categories" }).uncheck();
  await expect(page.getByTestId("category")).toHaveCount(0);
});
