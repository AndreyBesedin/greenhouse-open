import { expect, type Page, test } from "@playwright/test";

import { CAMERA_PRESETS, DEFAULT_PRESET, PRESET_ORDER, type PresetName } from "../src/camera.ts";
import { formatPoint } from "../src/readouts.ts";
import type { Point3 } from "../src/world.ts";
import { mainView, onScreen } from "./view.ts";

const LABELS: Record<PresetName, string> = {
  top: "Top",
  front: "Front",
  side: "Side",
  isometric: "Isometric",
};
const DEFAULT_VIEW = formatPoint(CAMERA_PRESETS[DEFAULT_PRESET].position);

async function viewCentre(page: Page): Promise<{ x: number; y: number }> {
  const box = await page.locator("canvas").boundingBox();
  if (box === null) {
    throw new Error("the 3D view is not on the page");
  }
  return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
}

test("each preset button moves the camera to its pose", async ({ page }) => {
  await page.goto("/");
  const camera = page.getByTestId("camera-position");

  for (const preset of PRESET_ORDER) {
    await page.getByRole("button", { name: LABELS[preset] }).click();
    await expect(camera).toHaveText(formatPoint(CAMERA_PRESETS[preset].position));
  }
});

test("dragging orbits the camera, and a refresh restores the default view", async ({ page }) => {
  await page.goto("/");
  const camera = page.getByTestId("camera-position");
  await expect(camera).toHaveText(DEFAULT_VIEW);

  const centre = await viewCentre(page);
  await page.mouse.move(centre.x, centre.y);
  await page.mouse.down();
  await page.mouse.move(centre.x + 200, centre.y + 60, { steps: 10 });
  await page.mouse.up();
  await expect(camera).not.toHaveText(DEFAULT_VIEW);

  await page.reload();
  await expect(camera).toHaveText(DEFAULT_VIEW);
});

test("the HUD reports frame rate, objects and the pointer on the ground", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByTestId("frame-rate")).toHaveText(/^\d+ fps$/);
  await expect(page.getByTestId("object-count")).toHaveText(/^[1-9]\d*$/);

  // The default view looks at the origin, so the middle of the view is on the ground there.
  const centre = await viewCentre(page);
  await page.mouse.move(centre.x, centre.y);
  await expect(page.getByTestId("pointer-position")).toHaveText(/^x -?0\.\d\d, y -?0\.\d\d$/);
});

// A mouse wheel's notch, as Chromium reports it.
const NOTCH_PX = 100;
// The HUD writes positions to the centimetre; a point worked out from them,
// or read again from where the pointer meets the ground, may differ by that.
const READOUT_M = 0.03;
// The climate box's floor, seen through its front wall from the default view.
const ON_ITS_FLOOR = { x: 2, y: 1, z: 0 };

/** A position as the HUD writes it, in world metres: the camera's, or where
 * the pointer meets the ground, whose z is 0. */
async function shownPoint(page: Page, testId: string): Promise<Point3> {
  const text = (await page.getByTestId(testId).textContent()) ?? "";
  const [x = Number.NaN, y = Number.NaN, z = 0] = (text.match(/-?\d+\.\d+/g) ?? []).map(Number);
  return { x, y, z };
}

function distance(a: Point3, b: Point3): number {
  return Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
}

/** How far `point` lies off the line from `from` through `towards`. */
function offTheLine(point: Point3, from: Point3, towards: Point3): number {
  const along = distance(from, towards);
  const t =
    ((point.x - from.x) * (towards.x - from.x) +
      (point.y - from.y) * (towards.y - from.y) +
      (point.z - from.z) * (towards.z - from.z)) /
    (along * along);
  return distance(point, {
    x: from.x + t * (towards.x - from.x),
    y: from.y + t * (towards.y - from.y),
    z: from.z + t * (towards.z - from.z),
  });
}

async function turnWheel(page: Page, notches: number): Promise<void> {
  for (let notch = 0; notch < Math.abs(notches); notch += 1) {
    await page.mouse.wheel(0, Math.sign(notches) * NOTCH_PX);
  }
}

test("the wheel zooms towards the greenhouse under the pointer, which stays under it", async ({
  page,
}) => {
  await page.goto("/?scenario=climate_box");
  await expect(page.getByTestId("scene-status")).toContainText("climate_box, day 0");
  const camera = page.getByTestId("camera-position");
  await expect(camera).toHaveText(DEFAULT_VIEW);
  const from = CAMERA_PRESETS[DEFAULT_PRESET].position;
  // A whole pixel, so that the wheel's notches and the pointer's readout
  // take the same ray.
  const drawn = await onScreen(page, ON_ITS_FLOOR);
  const at = { x: Math.round(drawn.x), y: Math.round(drawn.y) };
  await page.mouse.move(at.x, at.y);
  await expect(page.getByTestId("pointer-position")).toHaveText(/^x -?\d+\.\d\d, y -?\d+\.\d\d$/);
  const ground = await shownPoint(page, "pointer-position");
  expect(distance(ground, ON_ITS_FLOOR)).toBeLessThan(READOUT_M);

  await turnWheel(page, -20);

  // Along the ray through the pointer, a good way towards what it is over.
  await expect
    .poll(async () => distance(await shownPoint(page, "camera-position"), from))
    .toBeGreaterThan(1);
  const near = await shownPoint(page, "camera-position");
  expect(offTheLine(near, from, ground)).toBeLessThan(READOUT_M);
  expect(distance(near, ground)).toBeLessThan(distance(from, ground) - 1);
  // The floor stays under the pointer: read again, the ground there is the same.
  await page.mouse.move(at.x + 1, at.y);
  await page.mouse.move(at.x, at.y);
  await expect
    .poll(async () => distance(await shownPoint(page, "pointer-position"), ground))
    .toBeLessThan(READOUT_M);

  await page.getByRole("button", { name: "Isometric" }).click();
  await expect(camera).toHaveText(DEFAULT_VIEW);
});

test("over the sky, the wheel zooms towards the middle of the view, as before", async ({
  page,
}) => {
  await page.goto("/");
  const camera = page.getByTestId("camera-position");
  await page.getByRole("button", { name: "Front" }).click();
  await expect(camera).toHaveText(formatPoint(CAMERA_PRESETS.front.position));
  const box = await mainView(page).boundingBox();
  if (box === null) {
    throw new Error("the 3D view is not on the page");
  }
  // The front view stands on the ground: above the middle of the view is sky.
  await page.mouse.move(box.x + box.width / 2 - 100, box.y + box.height / 4);

  await turnWheel(page, -10);

  // Nearer the origin, where the view looks, and still on the way there.
  await expect.poll(async () => (await shownPoint(page, "camera-position")).y).toBeGreaterThan(-8);
  const near = await shownPoint(page, "camera-position");
  expect(near.x).toBeCloseTo(0, 2);
  expect(near.z).toBeCloseTo(0, 2);
  expect(near.y).toBeLessThan(0);
});
