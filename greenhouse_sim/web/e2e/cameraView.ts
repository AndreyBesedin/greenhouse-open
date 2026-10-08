import type { Page } from "@playwright/test";

import type { CameraPose } from "../src/camera.ts";
import { type CameraSpec, pixelAt } from "../src/sensors/camera.ts";

/** A camera pose as the address writes it. */
export function cameraText({ position, target }: CameraPose): string {
  return [position, target].map(({ x, y, z }) => `${x}:${y}:${z}`).join(",");
}

/** Points at the middle of a scene camera's picture's pixel (u, v). */
export async function pointAtPixel(
  page: Page,
  spec: CameraSpec,
  u: number,
  v: number,
): Promise<void> {
  const box = await page.getByTestId("camera-view").boundingBox();
  if (box === null) {
    throw new Error("the camera's picture is not on the page");
  }
  await page.mouse.move(
    box.x + ((u + 0.5) * box.width) / spec.width,
    box.y + ((v + 0.5) * box.height) / spec.height,
  );
}

/** How far ahead of a scene camera, along the way it looks, the ray through
 * the middle of pixel (u, v) meets the plane across the house at `x`. */
export function aheadAt(spec: CameraSpec, u: number, v: number, x: number): number {
  const metreAhead = pixelAt(spec, u + 0.5, v + 0.5, 1);
  return (x - spec.eye.x) / (metreAhead.x - spec.eye.x);
}

/** The depth a camera's pixel readout shows, in metres, or NaN if none. */
export function shownDepth(readout: string | null): number {
  const shown = /, ([\d.]+) m ahead$/.exec(readout ?? "");
  return Number(shown?.[1] ?? Number.NaN);
}
