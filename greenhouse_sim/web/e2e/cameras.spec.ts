import { expect, type Page, test } from "@playwright/test";

import type { CameraPose } from "../src/camera.ts";
import type { CameraSpec } from "../src/sensors/camera.ts";
import { aheadAt, cameraText, pointAtPixel, shownDepth } from "./cameraView";
import { selectAt } from "./view";

// The climate box's camera, at the front of the house, 2.2 m up, looking down
// it at the heater, as its layout places it; a point on its body, seen from
// behind and beside it.
const FRONT_CAMERA: CameraSpec = {
  cameraId: "front_camera",
  eye: { x: 0.6, y: 3.2, z: 2.2 },
  target: { x: 11, y: 3.2, z: 0.6 },
  width: 640,
  height: 480,
  fx: 457.007,
  fy: 457.007,
  ppx: 320,
  ppy: 240,
};
const CAMERA_BODY = { x: 0.66, y: 3.2, z: 2.2 };
const BEHIND_THE_CAMERA: CameraPose = {
  position: { x: 2.2, y: 3.6, z: 2.5 },
  target: CAMERA_BODY,
};
const AT_THE_CAMERA = `/?scenario=climate_box&camera=${cameraText(BEHIND_THE_CAMERA)}`;
// Where the middle of the heater and of the dehumidifier land on its picture,
// as the simulator projects them (tests/test_sensors.py).
const HEATER_PIXEL = { u: 426.6, v: 238.7 };
const DEHUMIDIFIER_PIXEL = { u: 98.3, v: 294.3 };
// A colour is red when its red channel is this much above its others, and
// grey when its channels are this close.
const REDDER_BY = 40;
const GREY_WITHIN = 12;

async function selectTheCamera(page: Page): Promise<void> {
  await page.goto(AT_THE_CAMERA);
  await expect(page.getByTestId("scene-status")).toContainText("climate_box, day 0, 127 entities");
  await selectAt(page, CAMERA_BODY, "climate_box_front_camera", BEHIND_THE_CAMERA);
}

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
      { u, v, width: FRONT_CAMERA.width, height: FRONT_CAMERA.height },
    );
}

function isRed([r, g, b]: [number, number, number]): boolean {
  return r > g + REDDER_BY && r > b + REDDER_BY;
}

function isGrey([r, g, b]: [number, number, number]): boolean {
  return Math.max(r, g, b) - Math.min(r, g, b) <= GREY_WITHIN;
}

test("cameras: a camera's picture is the scene as its intrinsics project it", async ({ page }) => {
  await selectTheCamera(page);
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

// The climate box from outside its right side wall, through the glass, and a
// point on the heater's side facing that way (`equipment.spec.ts`).
const ACROSS: CameraPose = {
  position: { x: 6, y: -8, z: 4 },
  target: { x: 6, y: 3.2, z: 1.2 },
};
const HEATER_SIDE = { x: 11.2, y: 0.3, z: 0.6 };
// The heater's face toward the camera, a plane across the house.
const HEATER_FRONT_X = 10.9;
// A depth is shown to the centimetre.
const CENTIMETRE = 0.01;

test("cameras: the instance pass names what the main view picks, and depth is a surface's distance", async ({
  page,
}) => {
  const u = Math.floor(HEATER_PIXEL.u);
  const v = Math.floor(HEATER_PIXEL.v);

  await test.step("the main view picks the heater", async () => {
    await page.goto(`/?scenario=climate_box&camera=${cameraText(ACROSS)}`);
    await expect(page.getByTestId("scene-status")).toContainText(
      "climate_box, day 0, 127 entities",
    );
    await selectAt(page, HEATER_SIDE, "climate_box_heater", ACROSS);
  });

  await test.step("the camera's passes name it where the simulator projects it", async () => {
    await selectTheCamera(page);
    const panel = page.getByRole("region", { name: "Camera" });
    const pixel = panel.getByTestId("camera-pixel");
    await expect(pixel).toHaveText("Point at the picture to read what each pixel shows.");

    await pointAtPixel(page, FRONT_CAMERA, u, v);
    await expect(pixel).toContainText(`Pixel (${u}, ${v}): climate_box_heater, `);
    // Its front face's distance ahead, to the centimetre shown.
    const ahead = aheadAt(FRONT_CAMERA, u, v, HEATER_FRONT_X);
    expect(Math.abs(shownDepth(await pixel.textContent()) - ahead)).toBeLessThanOrEqual(CENTIMETRE);
  });

  await test.step("the passes are pictures of their own, apart from the camera's", async () => {
    const panel = page.getByRole("region", { name: "Camera" });
    await expect(panel.getByTestId("camera-pass")).toHaveCount(0);

    await panel.getByRole("tab", { name: "Depth" }).click();
    await expect(panel.getByTestId("camera-pass")).toBeVisible();
    await expect(panel.getByTestId("camera-depth-range")).toHaveText(
      /^Depth ahead, on a log scale: white at [\d.]+ m, black at [\d.]+ m and where nothing is\.$/,
    );

    await panel.getByRole("tab", { name: "Instance" }).click();
    const inView = panel.getByRole("list", { name: "Entities in view" });
    await expect(inView.getByText(/^climate_box_heater: [\d,]+ px$/)).toBeVisible();
    await expect(inView.getByText(/^climate_box_dehumidifier: [\d,]+ px$/)).toBeVisible();
    // The fan hangs above the camera, out of its view.
    await expect(inView.getByText(/^climate_box_fan: /)).toHaveCount(0);

    await panel.getByRole("tab", { name: "RGB" }).click();
    await expect(panel.getByTestId("camera-pass")).toHaveCount(0);
  });
});

test("cameras: the run's log records each frame a camera takes", async ({ page }) => {
  await page.goto(`${AT_THE_CAMERA}&field=climate&t=600`);
  await expect(page.getByTestId("climate-time")).toHaveText("10 min", { timeout: 20_000 });
  await selectAt(page, CAMERA_BODY, "climate_box_front_camera", BEHIND_THE_CAMERA);
  const frames = page.getByRole("region", { name: "Frames" });

  // A frame a minute, from the run's start.
  await expect(frames.getByTestId("camera-frames")).toHaveText(
    "11 frames by 10 min, each RGB and depth.",
  );
  await expect(frames.getByTestId("camera-frame-id")).toHaveText(
    "sim_front_camera_20251231T231000Z_frame",
  );
  await expect(frames.getByTestId("camera-frame-from")).toHaveText("x 0.60, y 3.20, z 2.20");
  // Down the house, and down at the heater.
  await expect(frames.getByTestId("camera-frame-looking")).toHaveText("along the house, 8.7° down");
  await expect(frames.getByTestId("camera-frame-picture")).toHaveText(
    "640 × 480 px, fx 457.01 px, fy 457.01 px",
  );
  await expect(
    frames.getByRole("list", { name: "Frames taken" }).getByRole("listitem"),
  ).toHaveCount(11);
});
