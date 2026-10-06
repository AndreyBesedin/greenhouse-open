import { expect, test } from "@playwright/test";

import { selectAt } from "./view";

// gh_001's first row runs along y = 2.4 m from x = 1.75 to 6.25 m, on a tomato
// gutter reaching 0.25 m beyond each end: 0.3 m wide, its top at 0.6 m, on
// three legs, with a stone wool slab along it. The default camera looks from
// the front right, so it sees each part's front side.
const GUTTER_SIDE = { x: 3.0, y: 2.4 - 0.15, z: 0.54 };
const FIRST_LEG = { x: 1.5, y: 2.4, z: 0.25 };
// Between the first two plants, on the slab's top.
const SLAB_TOP = { x: 2.0, y: 2.4, z: 0.675 };

test("gh_001's rows stand on gutters, with legs and a slab", async ({ page }) => {
  await page.goto("/?scenario=gh_001");
  await expect(page.getByTestId("scene-status")).toContainText("gh_001, day 0, 147 entities");
  const inspector = page.getByRole("region", { name: "Inspector" });
  const shape = page.getByTestId("selected-shape");
  const material = page.getByTestId("selected-material");

  await selectAt(page, GUTTER_SIDE, "gh_001_row_1_support_1");
  await expect(inspector.getByText("CROP_GUTTER", { exact: true })).toBeVisible();
  await expect(shape).toHaveText("box, 5.00 × 0.30 × 0.12 m");
  await expect(material).toHaveText("steel");

  await selectAt(page, FIRST_LEG, "gh_001_row_1_support_1_leg_1");
  await expect(inspector.getByText("CROP_GUTTER", { exact: true })).toBeVisible();
  await expect(shape).toHaveText("cylinder, radius 0.02 m, height 0.48 m");

  await selectAt(page, SLAB_TOP, "gh_001_row_1_slab_1");
  await expect(inspector.getByText("SLAB", { exact: true })).toBeVisible();
  await expect(material).toHaveText("substrate");
});
