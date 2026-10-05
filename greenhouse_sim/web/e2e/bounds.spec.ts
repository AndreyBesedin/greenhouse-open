import { expect, test } from "@playwright/test";

import { clickAt, selectAt } from "./view";

// The example scene's greenhouse (gh_demo) is 4 m long, 6.4 m wide and 4 m
// high, with its floor corner at the world's origin.
const FAR_EDGE_HALFWAY_UP = { x: 0, y: 6.4, z: 2 };
// Inside the greenhouse, over the ground and clear of the plants.
const INSIDE_OVER_THE_GROUND = { x: 1, y: 1, z: 1 };

test("the greenhouse's bounds are measured, labelled and selectable by their edges", async ({
  page,
}) => {
  await page.goto("/?scene=example");
  await expect(page.getByTestId("scene-status")).toContainText("9 entities");

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

  await selectAt(page, FAR_EDGE_HALFWAY_UP, "gh_demo_bounds");
  await expect(page.getByTestId("selected-shape")).toHaveText("box, 4.00 × 6.40 × 4.00 m");
  await expect(page.getByTestId("selected-position")).toHaveText("x 2.00, y 3.20, z 0.00");

  // The bounds' faces never take a click: it reaches what they enclose.
  await clickAt(page, INSIDE_OVER_THE_GROUND);
  await expect(page.getByTestId("selected-entity")).toHaveText("gh_demo_ground");
});
