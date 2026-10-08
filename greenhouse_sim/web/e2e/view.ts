import { expect, type Locator, type Page } from "@playwright/test";
import { PerspectiveCamera, Vector3 } from "three";

import {
  CAMERA_FIELD_OF_VIEW_DEG,
  CAMERA_PRESETS,
  type CameraPose,
  DEFAULT_PRESET,
  type PresetName,
} from "../src/camera.ts";
import { type Point3, worldToViewer } from "../src/world.ts";

/** The 3D view's canvas: a selected camera's picture is another. */
export function mainView(page: Page): Locator {
  return page.getByTestId("main-view").locator("canvas");
}

/** Where a world point appears on the page, seen from a camera preset or
 * pose, worked out as the viewer's own camera works it out. */
export async function onScreen(
  page: Page,
  point: Point3,
  preset: PresetName | CameraPose = DEFAULT_PRESET,
): Promise<{ x: number; y: number }> {
  const box = await mainView(page).boundingBox();
  if (box === null) {
    throw new Error("the 3D view is not on the page");
  }
  const camera = new PerspectiveCamera(CAMERA_FIELD_OF_VIEW_DEG, box.width / box.height);
  const pose = typeof preset === "string" ? CAMERA_PRESETS[preset] : preset;
  const position = worldToViewer(pose.position);
  const target = worldToViewer(pose.target);
  camera.position.set(position.x, position.y, position.z);
  camera.lookAt(target.x, target.y, target.z);
  camera.updateMatrixWorld();
  const viewer = worldToViewer(point);
  const projected = new Vector3(viewer.x, viewer.y, viewer.z).project(camera);
  return {
    x: box.x + ((projected.x + 1) / 2) * box.width,
    y: box.y + ((1 - projected.y) / 2) * box.height,
  };
}

// Near the top of the view the camera looks past the ground grid at the sky.
// The default camera looks at the world origin, where a scenario's greenhouse
// has its corner; the greenhouse fills the view to the right of the middle
// line and rises above it, so the sky is clicked to the left.
const SKY_MARGIN_PX = 30;
const SKY_OFFSET_PX = -120;

export async function clickAt(
  page: Page,
  point: Point3,
  preset: PresetName | CameraPose = DEFAULT_PRESET,
): Promise<void> {
  const target = await onScreen(page, point, preset);
  await page.mouse.click(target.x, target.y);
}

/** Clicks the sky, where there is nothing to select. */
export async function clickSky(page: Page): Promise<void> {
  const box = await mainView(page).boundingBox();
  if (box === null) {
    throw new Error("the 3D view is not on the page");
  }
  await page.mouse.click(box.x + box.width / 2 + SKY_OFFSET_PX, box.y + SKY_MARGIN_PX);
}

/** Clicks a world point until the inspector shows `entityId`: a view that has
 * only just received its scene may not have drawn it yet, and a click then
 * passes through where the entity will be. */
export async function selectAt(
  page: Page,
  point: Point3,
  entityId: string,
  preset: PresetName | CameraPose = DEFAULT_PRESET,
): Promise<void> {
  const selected = page.getByTestId("selected-entity");
  await expect(async () => {
    await clickAt(page, point, preset);
    await expect(selected).toHaveText(entityId, { timeout: 500 });
  }).toPass();
}
