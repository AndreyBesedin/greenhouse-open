import { expect, test } from "@playwright/test";

import type { CameraPose } from "../src/camera.ts";
import { selectAt } from "./view";

// The compartment's main path runs across its front (x from 0 to 2 m), and
// side paths along both side walls; its back, from x = 22.7 m, is a service
// area, 23 m from where the camera presets look.
const MAIN_PATH = { x: 1.0, y: 4.0, z: 0.02 };
// Inside the service area, a metre up, seen steeply from above and beyond
// the back wall: the zone is picked before the floor and glazing behind it.
// (A zone yields to anything solid along the click, as glass does, so the
// click must land on the floor inside it rather than cross the rows.)
const IN_THE_SERVICE_AREA = { x: 23.3, y: 6.0, z: 1.0 };
const BEHIND_THE_BACK: CameraPose = {
  position: { x: 26, y: 6.0, z: 8 },
  target: IN_THE_SERVICE_AREA,
};

test("the compartment's paths and zones are coloured and picked by what they are", async ({
  page,
}) => {
  await page.goto("/?scenario=tomato_compartment");
  await expect(page.getByTestId("scene-status")).toContainText(
    "tomato_compartment, day 0, 896 entities",
  );

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
  await selectAt(page, MAIN_PATH, "tomato_compartment_main_path");
  await expect(inspector.getByText("WALKWAY", { exact: true })).toBeVisible();
  await expect(page.getByTestId("property-obstructs_movement")).toHaveText("false");
  // A zone is picked before what lies behind it, seen from a camera the
  // address places beyond the back of the house.
  const { position, target } = BEHIND_THE_BACK;
  const camera = [position, target].map(({ x, y, z }) => `${x}:${y}:${z}`).join(",");
  await page.goto(`/?scenario=tomato_compartment&camera=${camera}`);
  await expect(page.getByTestId("scene-status")).toContainText("896 entities");
  await selectAt(
    page,
    IN_THE_SERVICE_AREA,
    "tomato_compartment_service_area_back",
    BEHIND_THE_BACK,
  );
  await expect(page.getByTestId("selected-shape")).toHaveText("box, 14.00 × 1.20 × 2.20 m");
});
