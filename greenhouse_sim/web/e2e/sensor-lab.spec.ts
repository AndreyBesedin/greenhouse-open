import { expect, type Page, test } from "@playwright/test";

import type { CameraPose } from "../src/camera.ts";
import type { CameraSpec } from "../src/sensors/camera.ts";
import { aheadAt, cameraText, pointAtPixel, shownDepth } from "./cameraView";
import { selectAt } from "./view";

// P06's final QA, in the sensor lab: still air warming 0.5 °C a metre along
// the house from 16 °C at its front, ten minutes into a run.
const LAB_RUN = "/?scenario=sensor_lab&field=gradient&t=600";

// A point on each thermometer's face, and a pose 1.5 m from it.
function facing(x: number, y: number, side: 1 | -1): { face: Point; pose: CameraPose } {
  const face = { x: x + side * 0.04, y, z: 1.5 };
  return { face, pose: { position: { x: x + side * 1.5, y, z: 1.7 }, target: face } };
}
type Point = { x: number; y: number; z: number };
const CLEAN_FRONT = facing(3, 1.2, 1);
const IMPERFECT_FRONT = facing(3, 1.5, 1);
const CLEAN_BACK = facing(9, 1.2, -1);

// The lab's camera, at the front, 1.6 m up, looking down the house, as its
// layout places it; a point on its body, seen from behind and beside it.
const LAB_CAMERA: CameraSpec = {
  cameraId: "lab_camera",
  eye: { x: 0.6, y: 3.2, z: 1.6 },
  target: { x: 11, y: 3.2, z: 0.8 },
  width: 640,
  height: 480,
  fx: 457.007,
  fy: 457.007,
  ppx: 320,
  ppy: 240,
};
const CAMERA_BODY = { x: 0.66, y: 3.2, z: 1.6 };
const BEHIND_THE_CAMERA: CameraPose = {
  position: { x: 2.2, y: 3.6, z: 1.9 },
  target: CAMERA_BODY,
};
// Pixels where each box shows in the camera's picture, past the ones in
// front of it, and the plane across the house of each box's front face.
const BOXES = {
  near: { pixel: { u: 380, v: 300 }, frontX: 3.7 },
  middle: { pixel: { u: 290, v: 280 }, frontX: 6.7 },
  far: { pixel: { u: 258, v: 240 }, frontX: 9.7 },
};
// The middle box's front face, seen from between it and the near box.
const MIDDLE_FRONT = { x: 6.7, y: 3.4, z: 0.7 };
const BEFORE_THE_MIDDLE: CameraPose = { position: { x: 5.5, y: 3.4, z: 1 }, target: MIDDLE_FRONT };
// A depth is shown to the centimetre.
const CENTIMETRE = 0.01;

async function select(page: Page, layout: string, at: Point, entityId: string, pose: CameraPose) {
  await page.goto(`${LAB_RUN}${layout}&camera=${cameraText(pose)}`);
  await expect(page.getByTestId("scene-status")).toContainText("sensor_lab, day 0");
  await selectAt(page, at, entityId, pose);
}

test("sensor lab: each sensor stands where it is placed", async ({ page }) => {
  await select(page, "", CLEAN_FRONT.face, "sensor_lab_clean_front", CLEAN_FRONT.pose);
  await expect(page.getByTestId("selected-position")).toHaveText("x 3.00, y 1.20, z 1.46");
  await expect(page.getByTestId("property-sensor_kind")).toHaveText("temperature");
  await expect(page.getByTestId("property-noise_sd")).toHaveText("0");

  await select(page, "", IMPERFECT_FRONT.face, "sensor_lab_imperfect_front", IMPERFECT_FRONT.pose);
  await expect(page.getByTestId("selected-position")).toHaveText("x 3.00, y 1.50, z 1.46");
  await expect(page.getByTestId("property-noise_sd")).toHaveText("0.30");
  await expect(page.getByTestId("property-drift_per_hour")).toHaveText("1.20");
  await expect(page.getByTestId("property-dropout")).toHaveText("0.10");
});

test("sensor lab: clean sensors read the truth, on the gradient's line", async ({ page }) => {
  for (const [sensor, entityId, reading] of [
    [CLEAN_FRONT, "sensor_lab_clean_front", "17.50 °C at 10 min"],
    [CLEAN_BACK, "sensor_lab_clean_back", "20.50 °C at 10 min"],
  ] as const) {
    await select(page, "", sensor.face, entityId, sensor.pose);
    const panel = page.getByRole("region", { name: "Sensor" });
    await expect(panel.getByTestId("sensor-reading")).toHaveText(reading);
    await expect(panel.getByTestId("sensor-truth")).toHaveText(reading);
    // A reading every minute from the start, each on time.
    await expect(panel.locator(".sensor-chart-reading")).toHaveCount(11);
    await expect(panel.getByTestId("sensor-freshness")).toHaveText(
      "Fresh: its reading of 10 min has come.",
    );
  }
});

test("sensor lab: an imperfect sensor errs as configured, the same way every time", async ({
  page,
}) => {
  await select(page, "", IMPERFECT_FRONT.face, "sensor_lab_imperfect_front", IMPERFECT_FRONT.pose);
  const panel = page.getByRole("region", { name: "Sensor" });
  const imperfections = panel.getByRole("checkbox", { name: "Imperfections" });
  // Biased, drifting and noisy to a tenth of a degree, and 30 s late: by ten
  // minutes its latest is the one taken at nine. Its samples at three and
  // four minutes dropped out.
  const erring = async () => {
    await expect(panel.getByTestId("sensor-reading")).toHaveText("18.20 °C at 9 min");
    await expect(panel.getByTestId("sensor-truth")).toHaveText("17.50 °C at 10 min");
    await expect(panel.locator(".sensor-chart-reading")).toHaveCount(8);
  };
  await erring();

  await imperfections.uncheck();
  await expect(panel.getByTestId("sensor-reading")).toHaveText("17.50 °C at 10 min");
  await expect(panel.locator(".sensor-chart-reading")).toHaveCount(11);

  await imperfections.check();
  await erring();
  // And again, read afresh.
  await select(page, "", IMPERFECT_FRONT.face, "sensor_lab_imperfect_front", IMPERFECT_FRONT.pose);
  await erring();
});

test("sensor lab: the camera's views agree with one another and with the main view", async ({
  page,
}) => {
  await test.step("the main view picks the middle box", async () => {
    await select(page, "", MIDDLE_FRONT, "sensor_lab_box_middle", BEFORE_THE_MIDDLE);
  });

  await test.step("the camera's frustum, intrinsics and frames", async () => {
    await select(page, "", CAMERA_BODY, "sensor_lab_lab_camera", BEHIND_THE_CAMERA);
    const panel = page.getByRole("region", { name: "Camera" });
    await expect(panel.getByTestId("camera-intrinsics")).toHaveText(
      "lab_camera: 640 × 480 px, 70° across",
    );
    // A frame a minute, from the run's start.
    await expect(page.getByTestId("camera-frames")).toHaveText(
      "11 frames by 10 min, each RGB and depth.",
    );
  });

  await test.step("each box, past the one in front, is named where it shows, at its distance", async () => {
    const pixel = page.getByTestId("camera-pixel");
    for (const [name, { pixel: at, frontX }] of Object.entries(BOXES)) {
      await pointAtPixel(page, LAB_CAMERA, at.u, at.v);
      await expect(pixel).toContainText(`Pixel (${at.u}, ${at.v}): sensor_lab_box_${name}, `);
      const ahead = aheadAt(LAB_CAMERA, at.u, at.v, frontX);
      expect(Math.abs(shownDepth(await pixel.textContent()) - ahead)).toBeLessThanOrEqual(
        CENTIMETRE,
      );
    }
  });

  await test.step("all three are in view, each partly", async () => {
    const panel = page.getByRole("region", { name: "Camera" });
    await panel.getByRole("tab", { name: "Instance" }).click();
    const inView = panel.getByRole("list", { name: "Entities in view" });
    for (const name of Object.keys(BOXES)) {
      await expect(
        inView.getByText(new RegExp(`^sensor_lab_box_${name}: [\\d,]+ px$`)),
      ).toBeVisible();
    }
  });
});

test("sensor lab: what an obstacle hides from the camera is missing from its instance pass", async ({
  page,
}) => {
  await select(page, "", CAMERA_BODY, "sensor_lab_lab_camera", BEHIND_THE_CAMERA);
  const panel = page.getByRole("region", { name: "Camera" });
  await panel.getByRole("tab", { name: "Instance" }).click();
  const inView = panel.getByRole("list", { name: "Entities in view" });
  await expect(inView.getByText(/^sensor_lab_box_middle: /)).toBeVisible();

  // Its blocked layout moves the near box in front of the camera.
  await page.getByRole("combobox", { name: "Layout of sensor_lab" }).selectOption("blocked");
  await expect(page.getByTestId("scene-status")).toContainText("blocked layout");
  await expect(page.getByTestId("selected-entity")).toHaveText("sensor_lab_lab_camera");
  await expect(inView.getByText(/^sensor_lab_box_near: /)).toBeVisible();
  await expect(inView.getByText(/^sensor_lab_box_middle: /)).toHaveCount(0);
  await expect(inView.getByText(/^sensor_lab_box_far: /)).toHaveCount(0);
});
