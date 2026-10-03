import { expect, type Page, test } from "@playwright/test";

import { CAMERA_PRESETS, DEFAULT_PRESET, PRESET_ORDER, type PresetName } from "../src/camera.ts";
import { formatPoint } from "../src/readouts.ts";

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
