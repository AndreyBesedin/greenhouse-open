import { expect, test } from "@playwright/test";

import { selectAt } from "./view";

// gh_001's aisles run across its front (x from 0.1 to 1.3 m) and along its
// right side wall; its back, from x = 6.8 m, is a service zone.
const FRONT_AISLE = { x: 0.7, y: 4.0, z: 0.02 };
// Inside the service zone, a metre up, seen from the front: the zone is
// picked before the floor and glazing behind it.
const IN_THE_SERVICE_ZONE = { x: 7.35, y: 2.5, z: 1.0 };

test("gh_001's aisles and zones are coloured and picked by what they are", async ({ page }) => {
  await page.goto("/?scenario=gh_001");
  await expect(page.getByTestId("scene-status")).toContainText("gh_001, day 0, 165 entities");

  await page.getByRole("checkbox", { name: "Categories" }).check();
  await expect(page.getByTestId("layout-category")).toHaveText([
    "planting position",
    "crop gutter",
    "slab",
    "walkway",
    "service zone",
    "keep-out",
    "rail",
    "pipe",
    "wire",
    "obstacle",
  ]);
  await expect(page.getByTestId("category")).toHaveCount(7);

  const inspector = page.getByRole("region", { name: "Inspector" });
  await selectAt(page, FRONT_AISLE, "gh_001_front_aisle");
  await expect(inspector.getByText("WALKWAY", { exact: true })).toBeVisible();
  await expect(page.getByTestId("property-obstructs_movement")).toHaveText("false");
  // A zone is picked before what lies behind it. The legends would cover it.
  await page.getByRole("checkbox", { name: "Categories" }).uncheck();
  await inspector.getByRole("button", { name: "Clear selection" }).click();
  await page.getByRole("button", { name: "Front" }).click();
  await selectAt(page, IN_THE_SERVICE_ZONE, "gh_001_service_zone_back", "front");
  await expect(page.getByTestId("selected-shape")).toHaveText("box, 7.60 × 1.10 × 2.20 m");
});
