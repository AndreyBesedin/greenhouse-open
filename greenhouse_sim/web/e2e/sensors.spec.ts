import { expect, test } from "@playwright/test";

import type { CameraPose } from "../src/camera.ts";
import { selectAt } from "./view";

// The climate box's CO2 sensor, a housing 8 cm wide in the middle of the
// house, 1.5 m up, seen from 1.5 m in front of it; a point on its face.
const CO2_FACE = { x: 5.96, y: 3.2, z: 1.5 };
const BEFORE_IT: CameraPose = { position: { x: 4.5, y: 3.2, z: 1.7 }, target: CO2_FACE };

function cameraText({ position, target }: CameraPose): string {
  return [position, target].map(({ x, y, z }) => `${x}:${y}:${z}`).join(",");
}

test("sensors: a sensor stands where it is placed, and the inspector shows its configuration", async ({
  page,
}) => {
  await page.goto(`/?scenario=climate_box&camera=${cameraText(BEFORE_IT)}`);
  await expect(page.getByTestId("scene-status")).toContainText("climate_box, day 0, 121 entities");

  await selectAt(page, CO2_FACE, "climate_box_co2", BEFORE_IT);
  await expect(page.getByTestId("selected-type")).toHaveText("sensor");
  await expect(page.getByTestId("selected-shape")).toHaveText("box, 0.08 × 0.08 × 0.08 m");
  await expect(page.getByTestId("property-sensor_kind")).toHaveText("co2");
  await expect(page.getByTestId("property-unit")).toHaveText("ppm");
  await expect(page.getByTestId("property-cadence_s")).toHaveText("60");
  await expect(page.getByTestId("property-noise_sd")).toHaveText("0");

  // Coloured by category, the sensors have a legend of their own.
  await page.getByRole("checkbox", { name: "Categories" }).check();
  await expect(page.getByTestId("sensor-category")).toHaveText(["sensor"]);
});

// The climate box's back temperature sensor, by the heater's half of the
// house, 1.5 m up; a point on its face, seen from 1.5 m in front of it.
const BACK_FACE = { x: 8.96, y: 3.1, z: 1.5 };
const BEFORE_THE_BACK: CameraPose = { position: { x: 7.5, y: 3.1, z: 1.7 }, target: BACK_FACE };

test("sensors: a selected sensor shows its reading through a run, the truth beside it for QA", async ({
  page,
}) => {
  await page.goto(
    `/?scenario=climate_box&set=heater:1&field=climate&t=600&camera=${cameraText(BEFORE_THE_BACK)}`,
  );
  await expect(page.getByTestId("climate-time")).toHaveText("10 min", { timeout: 20_000 });

  await selectAt(page, BACK_FACE, "climate_box_temperature_back", BEFORE_THE_BACK);
  const panel = page.getByRole("region", { name: "Sensor" });
  // Clean, it reads the truth: ten minutes in, the heater has warmed its
  // half of the house.
  await expect(panel.getByTestId("sensor-reading")).toHaveText("18.59 °C at 10 min");
  await expect(panel.getByRole("complementary", { name: "Truth, for QA only" })).toBeVisible();
  await expect(panel.getByTestId("sensor-truth")).toHaveText("18.59 °C at 10 min");

  // Back at the start, it reads the starting air.
  await page.getByRole("slider", { name: "Time into the run" }).fill("0");
  await expect(panel.getByTestId("sensor-reading")).toHaveText("16 °C at 0 min");
});
