import { expect, type Page, test } from "@playwright/test";

import { CAMERA_CLOSEST_M, CAMERA_PRESETS, DEFAULT_PRESET } from "../src/camera.ts";
import { formatPoint } from "../src/readouts.ts";
import { mainView } from "./view.ts";

// The climate box's run, ten minutes into its first day: the lightest run
// whose day can change, which works its climate out again and draws its
// scene anew. The camera's controls are the same over every scene.
const RUN = "/?scenario=climate_box&field=climate&t=600";
// A moment on a later day takes the simulator a grid run of its own.
const ARRIVES = { timeout: 40_000 };
// A mouse wheel's notch, as Chromium reports it.
const NOTCH_PX = 100;
// The HUD writes the camera's position to the centimetre.
const ROUNDING_M = 0.01;
const DEFAULT_VIEW = formatPoint(CAMERA_PRESETS[DEFAULT_PRESET].position);

/** How far the camera stands from the world's origin, where the default view
 * looks, as the HUD shows its position, to the centimetre. */
async function fromTheOrigin(page: Page): Promise<number> {
  const shown = (await page.getByTestId("camera-position").textContent()) ?? "";
  return Math.hypot(...(shown.match(/-?\d+\.\d+/g) ?? []).map(Number));
}

/** Turns the wheel over the middle of the view by `notches`: in while
 * negative, as a wheel turned away from the user scrolls up a page. */
async function turnWheel(page: Page, notches: number): Promise<void> {
  const box = await mainView(page).boundingBox();
  if (box === null) {
    throw new Error("the 3D view is not on the page");
  }
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  for (let notch = 0; notch < Math.abs(notches); notch += 1) {
    await page.mouse.wheel(0, Math.sign(notches) * NOTCH_PX);
  }
}

test("close-up: zoomed in as far as it goes, the camera backs out after a change of day", async ({
  page,
}) => {
  test.setTimeout(120_000);
  const camera = page.getByTestId("camera-position");
  const moment = page.getByTestId("climate-time");
  await page.goto(RUN);
  await expect(moment).toHaveText("10 min", ARRIVES);
  await expect(camera).toHaveText(DEFAULT_VIEW);

  await test.step("a long zoom in stops at the camera's closest approach", async () => {
    // Towards what the middle of the view is over, at the house's corner: the
    // camera stops 20 cm short of it, which lies at or before the origin.
    await turnWheel(page, -300);
    await expect.poll(() => fromTheOrigin(page)).toBeLessThan(2 * CAMERA_CLOSEST_M);
    expect(await fromTheOrigin(page)).toBeGreaterThanOrEqual(CAMERA_CLOSEST_M - ROUNDING_M);
  });

  await test.step("a day on, the wheel backs it away again", async () => {
    await page
      .getByRole("group", { name: "Climate run" })
      .getByRole("button", { name: "Next day" })
      .click();
    await expect(moment).toHaveText("day 1, 10 min", ARRIVES);
    // Each notch out takes it a twentieth further away: 40 of them, nearly
    // eight times as far.
    await turnWheel(page, 40);
    await expect.poll(() => fromTheOrigin(page)).toBeGreaterThan(1);
  });

  await test.step("and a preset returns it to its view", async () => {
    await page.getByRole("button", { name: "Isometric" }).click();
    await expect(camera).toHaveText(DEFAULT_VIEW);
  });
});
