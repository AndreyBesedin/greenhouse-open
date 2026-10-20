import { expect, type Page, test } from "@playwright/test";

import type { CameraPose } from "../src/camera.ts";
import type { Point3 } from "../src/world.ts";
import { clickSky, onScreen, selectAt } from "./view";

// The climate box seen from outside its right side wall, through the glass,
// as equipment.spec.ts sees it: the heater in its back right corner, its
// base at (11.2, 0.7), its box 0.6 m by 0.8 m; a point on its side facing
// the camera, and its foot below it.
const ACROSS: CameraPose = {
  position: { x: 6, y: -8, z: 4 },
  target: { x: 6, y: 3.2, z: 1.2 },
};
const HEATER_SIDE = { x: 11.2, y: 0.3, z: 0.6 };
const HEATER_FOOT = { x: 11.2, y: 0.3, z: 0 };
// A metre towards the front wall and half a metre into the house.
const MOVED_FOOT = { x: 10.2, y: 0.8, z: 0 };
const MOVED_SIDE = { x: 10.2, y: 0.8, z: 0.6 };
const MOVED = /[?&]layout=default~heater:-1:0\.5(&|$)/;

function cameraText({ position, target }: CameraPose): string {
  return [position, target].map(({ x, y, z }) => `${x}:${y}:${z}`).join(",");
}

/** Drags in the view from one world point to another, as the view sees
 * them, and lets go, unless told to hold on. */
async function drag(page: Page, from: Point3, to: Point3, letGo = true): Promise<void> {
  const start = await onScreen(page, from, ACROSS);
  const end = await onScreen(page, to, ACROSS);
  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  await page.mouse.move(end.x, end.y, { steps: 10 });
  if (letGo) {
    await page.mouse.up();
  }
}

test("moving: the heater is dragged across the floor, undone, cancelled, and Back takes a move back", async ({
  page,
}) => {
  const status = page.getByTestId("scene-status");
  const position = page.getByTestId("selected-position");
  const offset = page.getByTestId("move-offset");
  const move = page.getByRole("button", { name: "Move", exact: true });
  const done = page.getByRole("button", { name: "Done moving" });

  await test.step("a drag while moving moves the heater, and the address keeps it", async () => {
    await page.goto(`/?scenario=climate_box&camera=${cameraText(ACROSS)}`);
    await expect(status).toContainText("climate_box, day 0, 128 entities");
    // The view is coloured, as it stays while things are moved.
    await page.getByLabel("Colour by").selectOption("level");
    await selectAt(page, HEATER_SIDE, "climate_box_heater", ACROSS);
    await expect(offset).toHaveText("The heater stands where its layout places it.");
    await move.click();
    await expect(done).toHaveAttribute("aria-pressed", "true");

    await drag(page, HEATER_FOOT, MOVED_FOOT);

    await expect(page).toHaveURL(MOVED);
    await expect(position).toHaveText("x 10.20, y 1.20, z 0.00");
    await expect(offset).toHaveText(
      "The heater stands −1.0 m along x and +0.5 m along y from where its layout places it.",
    );
    await expect(status).toContainText("scenario climate_box, heater moved");
    await expect(page.getByLabel("Colour by")).toHaveValue("level");
  });

  await test.step("the view held still: the heater is picked where it now stands", async () => {
    await done.click();
    await clickSky(page);
    await expect(position).toHaveCount(0);
    await selectAt(page, MOVED_SIDE, "climate_box_heater", ACROSS);
    await expect(position).toHaveText("x 10.20, y 1.20, z 0.00");
  });

  await test.step("Undo move puts it back where it was", async () => {
    await page.getByRole("button", { name: "Undo move" }).click();
    await expect(page).not.toHaveURL(/layout=/);
    await expect(position).toHaveText("x 11.20, y 0.70, z 0.00");
    await expect(page.getByRole("button", { name: "Undo move" })).toBeDisabled();
    await expect(page.getByLabel("Colour by")).toHaveValue("level");
  });

  await test.step("Escape cancels a drag, and then stops moving", async () => {
    await move.click();
    await drag(page, HEATER_FOOT, MOVED_FOOT, false);
    await expect(offset).toHaveText(
      "The heater stands −1.0 m along x and +0.5 m along y from where its layout places it.",
    );
    await page.keyboard.press("Escape");
    await page.mouse.up();
    await expect(offset).toHaveText("The heater stands where its layout places it.");
    await expect(page).not.toHaveURL(/layout=/);
    await expect(done).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(move).toHaveAttribute("aria-pressed", "false");
  });

  await test.step("Back takes a move back too", async () => {
    await move.click();
    await drag(page, HEATER_FOOT, MOVED_FOOT);
    await expect(page).toHaveURL(MOVED);
    await expect(position).toHaveText("x 10.20, y 1.20, z 0.00");

    await page.goBack();

    await expect(page).not.toHaveURL(/layout=/);
    await expect(position).toHaveText("x 11.20, y 0.70, z 0.00");
  });
});
