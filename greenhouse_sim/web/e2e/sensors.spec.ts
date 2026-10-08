import { expect, type Page, test } from "@playwright/test";

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
  await expect(page.getByTestId("scene-status")).toContainText("climate_box, day 0, 122 entities");

  await selectAt(page, CO2_FACE, "climate_box_co2", BEFORE_IT);
  await expect(page.getByTestId("selected-type")).toHaveText("sensor");
  await expect(page.getByTestId("selected-shape")).toHaveText("box, 0.08 × 0.08 × 0.08 m");
  await expect(page.getByTestId("property-sensor_kind")).toHaveText("co2");
  await expect(page.getByTestId("property-unit")).toHaveText("ppm");
  await expect(page.getByTestId("property-cadence_s")).toHaveText("60");
  await expect(page.getByTestId("property-noise_sd")).toHaveText("10");
  await expect(page.getByTestId("property-latency_s")).toHaveText("60");

  // Coloured by category, the sensors and the camera have a legend of their own.
  await page.getByRole("checkbox", { name: "Categories" }).check();
  await expect(page.getByTestId("sensor-category")).toHaveText(["sensor", "camera"]);
});

// The climate box's front temperature sensor, which is clean, and its back
// one, by the heater, which errs; a point on each one's face, seen from
// 1.5 m beside it.
const FRONT_FACE = { x: 3.04, y: 3.1, z: 1.5 };
const BESIDE_THE_FRONT: CameraPose = {
  position: { x: 4.5, y: 3.1, z: 1.7 },
  target: FRONT_FACE,
};
const BACK_FACE = { x: 8.96, y: 3.1, z: 1.5 };
const BEFORE_THE_BACK: CameraPose = { position: { x: 7.5, y: 3.1, z: 1.7 }, target: BACK_FACE };
const HEATED_RUN = "/?scenario=climate_box&set=heater:1&field=climate&t=600";

test("sensors: a clean sensor's reading through a run is the truth beside it", async ({ page }) => {
  await page.goto(`${HEATED_RUN}&camera=${cameraText(BESIDE_THE_FRONT)}`);
  await expect(page.getByTestId("climate-time")).toHaveText("10 min", { timeout: 20_000 });

  await selectAt(page, FRONT_FACE, "climate_box_temperature_front", BESIDE_THE_FRONT);
  const panel = page.getByRole("region", { name: "Sensor" });
  // Ten minutes in, the unheated half of the house has cooled.
  await expect(panel.getByTestId("sensor-reading")).toHaveText("12.69 °C at 10 min");
  await expect(panel.getByRole("complementary", { name: "Truth, for QA only" })).toBeVisible();
  await expect(panel.getByTestId("sensor-truth")).toHaveText("12.69 °C at 10 min");
  // A reading a minute, on the truth's line.
  await expect(panel.locator(".sensor-chart-reading")).toHaveCount(11);

  // Back at the start, it reads the starting air.
  await page.getByRole("slider", { name: "Time into the run" }).fill("0");
  await expect(panel.getByTestId("sensor-reading")).toHaveText("16 °C at 0 min");
});

test("sensors: an imperfect sensor errs as configured, and the QA switch cleans it", async ({
  page,
}) => {
  await page.goto(`${HEATED_RUN}&camera=${cameraText(BEFORE_THE_BACK)}`);
  await expect(page.getByTestId("climate-time")).toHaveText("10 min", { timeout: 20_000 });

  await selectAt(page, BACK_FACE, "climate_box_temperature_back", BEFORE_THE_BACK);
  const panel = page.getByRole("region", { name: "Sensor" });
  // Biased, drifting and noisy, to a tenth of a degree, and 30 s late: by
  // ten minutes, its latest reading is the one taken at nine. Two of its
  // samples dropped out.
  await expect(panel.getByTestId("sensor-reading")).toHaveText("19.20 °C at 9 min");
  await expect(panel.getByTestId("sensor-truth")).toHaveText("18.59 °C at 10 min");
  await expect(panel.locator(".sensor-chart-reading")).toHaveCount(8);

  await panel.getByRole("checkbox", { name: "Imperfections" }).uncheck();
  await expect(panel.getByTestId("sensor-reading")).toHaveText("18.59 °C at 10 min");
  await expect(panel.locator(".sensor-chart-reading")).toHaveCount(11);
});

// The climate box's camera, at the front of the house, 2.2 m up, looking down
// it at the heater; a point on its body, seen from behind and beside it.
const CAMERA_BODY = { x: 0.66, y: 3.2, z: 2.2 };
const BEHIND_THE_CAMERA: CameraPose = {
  position: { x: 2.2, y: 3.6, z: 2.5 },
  target: CAMERA_BODY,
};
// Where the middle of the heater and of the dehumidifier land on its picture,
// as the simulator projects them (tests/test_sensors.py).
const PICTURE = { width: 640, height: 480 };
const HEATER_PIXEL = { u: 426.6, v: 238.7 };
const DEHUMIDIFIER_PIXEL = { u: 98.3, v: 294.3 };
// A colour is red when its red channel is this much above its others, and
// grey when its channels are this close.
const REDDER_BY = 40;
const GREY_WITHIN = 12;

/** The camera's picture's colour at a pixel, as its canvas drew it. */
async function pictureAt(
  page: Page,
  { u, v }: { u: number; v: number },
): Promise<[number, number, number]> {
  return page
    .getByTestId("camera-view")
    .locator("canvas")
    .evaluate(
      (canvas: HTMLCanvasElement, { u, v, width, height }) => {
        const copy = document.createElement("canvas");
        copy.width = canvas.width;
        copy.height = canvas.height;
        const context = copy.getContext("2d");
        if (context === null) {
          throw new Error("no 2D context to copy the picture into");
        }
        context.drawImage(canvas, 0, 0);
        const x = Math.floor((u * canvas.width) / width);
        const y = Math.floor((v * canvas.height) / height);
        const [r = 0, g = 0, b = 0] = context.getImageData(x, y, 1, 1).data;
        return [r, g, b] as [number, number, number];
      },
      { u, v, ...PICTURE },
    );
}

function isRed([r, g, b]: [number, number, number]): boolean {
  return r > g + REDDER_BY && r > b + REDDER_BY;
}

function isGrey([r, g, b]: [number, number, number]): boolean {
  return Math.max(r, g, b) - Math.min(r, g, b) <= GREY_WITHIN;
}

test("sensors: a camera's picture is the scene as its intrinsics project it", async ({ page }) => {
  await page.goto(`/?scenario=climate_box&camera=${cameraText(BEHIND_THE_CAMERA)}`);
  await expect(page.getByTestId("scene-status")).toContainText("climate_box, day 0, 122 entities");

  await selectAt(page, CAMERA_BODY, "climate_box_front_camera", BEHIND_THE_CAMERA);
  await expect(page.getByTestId("selected-type")).toHaveText("camera");
  const panel = page.getByRole("region", { name: "Camera" });
  await expect(panel.getByTestId("camera-intrinsics")).toHaveText(
    "front_camera: 640 × 480 px, 70° across",
  );

  // Both units are off, and grey, where the simulator says they land.
  await expect.poll(() => pictureAt(page, HEATER_PIXEL).then(isGrey)).toBe(true);
  await expect.poll(() => pictureAt(page, DEHUMIDIFIER_PIXEL).then(isGrey)).toBe(true);

  // Running, the heater shows red in the camera's picture as in the view.
  await page
    .getByRole("group", { name: "Equipment" })
    .getByRole("checkbox", { name: "heater" })
    .check();
  await expect.poll(() => pictureAt(page, HEATER_PIXEL).then(isRed)).toBe(true);
  await expect.poll(() => pictureAt(page, DEHUMIDIFIER_PIXEL).then(isGrey)).toBe(true);
});
