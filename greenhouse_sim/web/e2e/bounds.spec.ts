import { expect, test } from "@playwright/test";

import { clickAt, selectAt } from "./view";

// The example scene's greenhouse (gh_demo) is 4 m long, 6.4 m wide and 4 m
// high, with its floor corner at the world's origin.
// Inside the greenhouse, over the floor and clear of the plants.
const INSIDE_OVER_THE_FLOOR = { x: 1, y: 1, z: 1 };
// The middle of the right side wall's top edge, which no other surface shares.
const RIGHT_WALL_TOP = { x: 2, y: 0, z: 4 };

test("the greenhouse is measured and labelled, and its walls let clicks through", async ({
  page,
}) => {
  await page.goto("/?scene=example");
  await expect(page.getByTestId("scene-status")).toContainText("13 entities");

  await page.getByLabel("Dimensions and axis labels").check();
  await expect(page.getByTestId("debug-label")).toHaveText([
    "x",
    "y",
    "z",
    "length 4.00 m",
    "width 6.40 m",
    "height 4.00 m",
  ]);
  await page.getByLabel("Dimensions and axis labels").uncheck();
  await expect(page.getByTestId("debug-label")).toHaveCount(0);

  // The walls' glass never takes a click: it reaches what they enclose.
  await selectAt(page, INSIDE_OVER_THE_FLOOR, "gh_demo_floor");

  // A wall is selected by its frame. From above, its top edge is in view.
  await page.getByRole("button", { name: "Top" }).click();
  await selectAt(page, RIGHT_WALL_TOP, "gh_demo_side_wall_right", "top");
  await expect(page.getByTestId("selected-shape")).toHaveText("plane, 4.00 × 4.00 m");
  await expect(page.getByTestId("selected-position")).toHaveText("x 2.00, y 0.00, z 2.00");
  await clickAt(page, INSIDE_OVER_THE_FLOOR, "top");
  await expect(page.getByTestId("selected-entity")).toHaveText("gh_demo_floor");
});
