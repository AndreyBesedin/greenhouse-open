import { expect, type Page, test } from "@playwright/test";

import type { CameraPose } from "../src/camera.ts";
import { selectAt } from "./view";

function cameraText({ position, target }: CameraPose): string {
  return [position, target].map(({ x, y, z }) => `${x}:${y}:${z}`).join(",");
}

// The solar lab's row of plants stands along the middle of the house, 20 cm
// of stem on a crop gutter whose slab tops out 0.675 m up; the crates south
// of its first four plants shade them at noon. Each plant is picked by its
// stem, seen from the north, clear of the crates.
const SHADED_STEM = { x: 2.25, y: 3.2, z: 0.78 };
const EXPOSED_STEM = { x: 9.75, y: 3.2, z: 0.78 };
const fromTheNorth = (stem: typeof SHADED_STEM): CameraPose => ({
  position: { x: stem.x, y: 5.0, z: 0.9 },
  target: stem,
});
// Solar noon at the March equinox, at 4.5° east: 12:50 on the site's clock.
const NOON_S = 46_200;

/** The solar lab at the equinox's noon, its camera looking at a stem. */
async function atNoon(page: Page, stem: typeof SHADED_STEM): Promise<void> {
  await page.goto(
    `/?scenario=solar_lab&field=climate&t=${NOON_S}&camera=${cameraText(fromTheNorth(stem))}`,
  );
  await expect(page.getByTestId("climate-time")).toHaveText("12 h 50 min");
  await expect(page.getByTestId("field-status")).toContainText("cells", { timeout: 60_000 });
}

test("solar lab: at the equinox's noon a shaded plant takes no beam and an exposed one a thousand micromoles", async ({
  page,
}) => {
  await test.step("behind the crates, a plant takes none of the beam", async () => {
    await atNoon(page, SHADED_STEM);
    // The sun 38° up in the south lights the scene.
    await expect(page.getByTestId("main-view")).toHaveAttribute("data-light", "sun");
    await selectAt(page, SHADED_STEM, "solar_lab_plant_001", fromTheNorth(SHADED_STEM));
    await expect(page.getByTestId("plant-par")).toHaveText("0 µmol/m²/s");
    await expect(page.getByTestId("plant-daily-light")).toHaveText("7.1 mol/m²/d");
  });

  await test.step("in the open, a plant takes the noon sun through the roof", async () => {
    await atNoon(page, EXPOSED_STEM);
    await selectAt(page, EXPOSED_STEM, "solar_lab_plant_016", fromTheNorth(EXPOSED_STEM));
    await expect(page.getByTestId("plant-par")).toHaveText("1094 µmol/m²/s");
    await expect(page.getByTestId("plant-daily-light")).toHaveText("27.3 mol/m²/d");
  });
});
