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

test("solar lab: at the equinox's noon a shaded plant takes the sky's light and an exposed one the sun's too", async ({
  page,
}) => {
  // Its climate run is worked out to noon first, and again under cloud.
  test.setTimeout(150_000);
  await test.step("behind the crates, a plant takes only the sky's light", async () => {
    await atNoon(page, SHADED_STEM);
    // The sun 38° up in the south lights the scene, and has warmed the shut
    // house well above the outside, 14.4 °C then (P08.8).
    await expect(page.getByTestId("main-view")).toHaveAttribute("data-light", "sun");
    await expect(
      page.getByRole("figure", { name: "House air" }).getByTestId("house-air-°C"),
    ).toHaveText("Air 29.5 °C, all off 29.5 °C");
    const weather = page.getByRole("region", { name: "Weather" });
    await expect(weather.getByTestId("weather-summary")).toContainText("14.4 °C");
    await selectAt(page, SHADED_STEM, "solar_lab_plant_001", fromTheNorth(SHADED_STEM));
    await expect(page.getByTestId("plant-par")).toHaveText("198 µmol/m²/s");
    await expect(page.getByTestId("plant-daily-light")).toHaveText("11.2 mol/m²/d");
  });

  await test.step("in the open, a plant takes the noon sun through the roof", async () => {
    await atNoon(page, EXPOSED_STEM);
    await selectAt(page, EXPOSED_STEM, "solar_lab_plant_016", fromTheNorth(EXPOSED_STEM));
    await expect(page.getByTestId("plant-par")).toHaveText("1069 µmol/m²/s");
    await expect(page.getByTestId("plant-daily-light")).toHaveText("26.9 mol/m²/d");
  });

  await test.step("under a full sky of cloud, it takes hardly more than the shaded one", async () => {
    const weather = page.getByRole("region", { name: "Weather" });
    await weather.getByTestId("weather-summary").click();
    await weather.getByRole("slider", { name: "Cloud cover" }).fill("100");
    await expect(page).toHaveURL(/&clouds=100(&|$)/);
    await expect(weather.getByTestId("weather-clouds")).toHaveText("100%, for QA");
    await expect(page.getByTestId("plant-par")).toHaveText("243 µmol/m²/s", { timeout: 60_000 });
    await expect(weather.getByTestId("weather-light")).toHaveText(
      "154 W/m², 98% of it the sky's, PAR 331 µmol/m²/s",
    );
  });
});

// P08's equinox views, drawn from the files the simulator writes: the sun
// where it stands at each moment, lighting the scene. Their screenshots are
// e2e/visual/solar.spec.ts.
const EQUINOX_VIEWS = {
  morning: "19.3° up, at 117° (ESE)",
  noon: "38.0° up, at 180° (S)",
  evening: "20.7° up, at 241° (WSW)",
};

for (const [view, sun] of Object.entries(EQUINOX_VIEWS)) {
  test(`solar lab: the equinox's ${view} view is lit from the sun at ${sun}`, async ({ page }) => {
    await page.goto(`/qa/solar-lab?view=${view}`);

    await expect(page.getByTestId("qa-caption")).toHaveText(`Solar QA, ${view} view: sun ${sun}`);
    await expect(page.getByTestId("main-view")).toHaveAttribute("data-light", "sun");
    await expect(page.getByTestId("field-legend-quantity")).toHaveText("PAR (µmol/m²/s)");
  });
}
