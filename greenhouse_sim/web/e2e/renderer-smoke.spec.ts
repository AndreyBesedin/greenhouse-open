import { expect, type Page, test } from "@playwright/test";

import { CAMERA_PRESETS, PRESET_ORDER, type PresetName } from "../src/camera.ts";
import { DEFAULT_QA_SEED, QA_RENDERER_PATH, QA_SELECTED_ID } from "../src/qa/qaPage.ts";
import {
  DEFAULT_STRESS_PLANTS,
  PLANTS_PER_ROW,
  stressPlantId,
  stressPlantPosition,
} from "../src/qa/stressScene.ts";
import { formatPoint } from "../src/readouts.ts";
import { simulatedDay } from "./hud";
import { selectAt } from "./view";

/**
 * P00's final QA, `renderer-smoke`: one walk through everything the renderer
 * does, as a person would use it. It runs as its own project once every other
 * browser test has passed (playwright.config.ts), so it can drive a shared
 * live run without disturbing them. The screenshot itself is compared in
 * CI's visual checks job, in its pinned container.
 */

const SCENARIO = "climate_box";
const LIVE = `/api/scenarios/${SCENARIO}/live`;
const PLANT = "climate_box_plant_001";
// Low on the plant's stem, which is at least 20 cm tall on any day, above its
// gutter's slab.
const PLANT_POINT = { x: 2.25, y: 2.4, z: 0.775 };
const REPLAY_DAYS = 3;
const PRESET_LABELS: Record<PresetName, string> = {
  top: "Top",
  front: "Front",
  side: "Side",
  isometric: "Isometric",
};
// A plant near the middle of the default stress field, in the row nearest the camera.
const STRESS_ROWS = DEFAULT_STRESS_PLANTS / PLANTS_PER_ROW;
const STRESS_COLUMN = PLANTS_PER_ROW / 2;
const STRESS_ROW = STRESS_ROWS / 2;
// A walk through every feature, with a live run stepping a day a second.
const WALKTHROUGH_TIMEOUT_MS = 120_000;
const DRAG_PX = { x: 160, y: 40 };

async function objectCount(page: Page): Promise<number> {
  return Number(await page.getByTestId("object-count").textContent());
}

async function stepTo(page: Page, day: number): Promise<void> {
  const controls = page.getByRole("group", { name: "Time controls" });
  await controls.getByRole("button", { name: "Step" }).click();
  await expect.poll(() => simulatedDay(page)).toBe(day);
}

async function replayFromReset(page: Page): Promise<string[]> {
  const controls = page.getByRole("group", { name: "Time controls" });
  await controls.getByRole("button", { name: "Reset" }).click();
  await expect.poll(() => simulatedDay(page)).toBe(0);
  for (let day = 1; day <= REPLAY_DAYS; day += 1) {
    await stepTo(page, day);
  }
  return page.locator('[data-testid^="property-"]').allTextContents();
}

test("renderer-smoke: the renderer, end to end", async ({ page }) => {
  test.setTimeout(WALKTHROUGH_TIMEOUT_MS);
  const controls = page.getByRole("group", { name: "Time controls" });
  const camera = page.getByTestId("camera-position");

  await test.step("Python moves a live scenario on, day by day", async () => {
    await page.request.post(`${LIVE}/play`);
    await page.request.post(`${LIVE}/speed?multiplier=1`);
    await page.goto(`/?live=${SCENARIO}`);
    await expect(page.getByTestId("stream-status")).toHaveText("live");
    await expect.poll(() => simulatedDay(page)).toBeGreaterThanOrEqual(0);
    const firstDay = await simulatedDay(page);
    await expect.poll(() => simulatedDay(page)).not.toBe(firstDay);
  });

  await test.step("each camera preset moves the camera to its pose", async () => {
    for (const preset of PRESET_ORDER) {
      await page.getByRole("button", { name: PRESET_LABELS[preset] }).click();
      await expect(camera).toHaveText(formatPoint(CAMERA_PRESETS[preset].position));
    }
  });

  await test.step("pause holds the day, reset returns to day 0, step moves one day", async () => {
    await controls.getByRole("button", { name: "Pause", exact: true }).click();
    await expect(controls.getByRole("button", { name: "Play", exact: true })).toBeVisible();
    await controls.getByRole("button", { name: "Reset" }).click();
    await expect.poll(() => simulatedDay(page)).toBe(0);
    await stepTo(page, 1);
  });

  let firstReplay: string[] = [];
  await test.step("a plant is selected, and the inspector follows it", async () => {
    await selectAt(page, PLANT_POINT, PLANT);
    await expect(page.getByTestId("selected-position")).toHaveText("x 2.25, y 2.40, z 0.67");
    firstReplay = await replayFromReset(page);
    expect(firstReplay.length).toBeGreaterThan(0);
  });

  await test.step("overlay boxes and arrows are drawn around it, and can be switched off", async () => {
    const overlays = page.getByRole("group", { name: "Overlays" });
    await expect(page.getByTestId("debug-label")).toHaveText(PLANT);
    await expect.poll(() => objectCount(page)).toBeGreaterThan(0);
    const withEverything = await objectCount(page);

    await overlays.getByLabel("Bounding box").uncheck();
    await expect.poll(() => objectCount(page)).toBeLessThan(withEverything);
    const withoutBox = await objectCount(page);
    await overlays.getByLabel("Origin and axes").uncheck();
    await expect.poll(() => objectCount(page)).toBeLessThan(withoutBox);

    await overlays.getByLabel("Bounding box").check();
    await overlays.getByLabel("Origin and axes").check();
    await expect.poll(() => objectCount(page)).toBe(withEverything);
  });

  await test.step("a reset replays the same days exactly", async () => {
    expect(await replayFromReset(page)).toEqual(firstReplay);
    await expect(page.getByTestId("selected-entity")).toHaveText(PLANT);
  });

  await test.step("playing again, Python moves it on", async () => {
    await controls.getByRole("button", { name: "Play", exact: true }).click();
    await expect.poll(() => simulatedDay(page)).toBeGreaterThan(REPLAY_DAYS);
  });

  await test.step("the screenshot baseline's page draws its seeded scene", async () => {
    await page.goto(`${QA_RENDERER_PATH}?seed=${DEFAULT_QA_SEED}`);
    await expect(page.getByTestId("debug-label")).toHaveText(QA_SELECTED_ID);
  });

  await test.step("the stress scene stays interactive", async () => {
    await page.goto("/");
    await page.getByRole("button", { name: "Stress scene" }).click();
    await expect(page.getByTestId("scene-status")).toContainText(
      `${DEFAULT_STRESS_PLANTS + 2} entities`,
    );
    await expect(page.getByTestId("draw-calls")).toHaveText(/^\d \(/);

    const view = await page.locator("canvas").boundingBox();
    if (view === null) {
      throw new Error("the 3D view is not on the page");
    }
    const before = await camera.textContent();
    await page.mouse.move(view.x + view.width / 2, view.y + view.height / 2);
    await page.mouse.down();
    await page.mouse.move(
      view.x + view.width / 2 + DRAG_PX.x,
      view.y + view.height / 2 + DRAG_PX.y,
      {
        steps: 8,
      },
    );
    await page.mouse.up();
    await expect(camera).not.toHaveText(before ?? "");

    await page.getByRole("button", { name: "Isometric" }).click();
    const plant = stressPlantPosition(STRESS_COLUMN, STRESS_ROW, STRESS_ROWS);
    await selectAt(
      page,
      { ...plant, z: 0.15 },
      stressPlantId(STRESS_ROW * PLANTS_PER_ROW + STRESS_COLUMN + 1),
    );
  });
});
