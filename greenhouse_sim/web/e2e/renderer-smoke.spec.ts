import { expect, type Page, test } from "@playwright/test";
import { CAMERA_PRESETS, PRESET_ORDER, type PresetName } from "../src/camera.ts";
import { DAY_S } from "../src/clock.ts";
import { VIEWER_PATH } from "../src/landing/paths";
import { DEFAULT_QA_SEED, QA_RENDERER_PATH, QA_SELECTED_ID } from "../src/qa/qaPage.ts";
import {
  DEFAULT_STRESS_PLANTS,
  PLANTS_PER_ROW,
  stressPlantId,
  stressPlantPosition,
} from "../src/qa/stressScene.ts";
import { formatPoint } from "../src/readouts.ts";
import { chooser } from "./chooser";
import { askForRun, computedTo, openReplay, stopRun } from "./replays";
import { selectAt } from "./view";

/**
 * P00's final QA, `renderer-smoke`: one walk through everything the renderer
 * does, as a person would use it, on a run a worker computes and its replay
 * plays. It runs as its own project once every other browser test has passed
 * (playwright.config.ts). The screenshot itself is compared in CI's visual
 * checks job, in its pinned container.
 */

const SCENARIO = "climate_box";
const PLANT = "climate_box_plant_001";
// Low on the plant's stem, which is at least 20 cm tall on any day, above its
// gutter's slab.
const PLANT_POINT = { x: 2.25, y: 2.4, z: 0.775 };
// The climate box's run: 14 days, computed before the replay plays them.
const RUN_END_S = 14 * DAY_S;
const ARRIVES = { timeout: 60_000 };
// The replay's quickest pace, in seconds a day.
const QUICK = "2";
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
// A walk through every feature, the run computed first.
const WALKTHROUGH_TIMEOUT_MS = 240_000;
const DRAG_PX = { x: 160, y: 40 };

async function objectCount(page: Page): Promise<number> {
  return Number(await page.getByTestId("object-count").textContent());
}

/** The scene's object count once it holds still for a second, or 0 while it
 * changes. */
async function steadyObjectCount(page: Page): Promise<number> {
  const before = await objectCount(page);
  await page.waitForTimeout(1000);
  return (await objectCount(page)) === before ? before : 0;
}

/** Where the replay stands, in seconds into the run, as its timeline says. */
async function reached(page: Page): Promise<number> {
  const handle = page.getByRole("slider", { name: "Position in the run" });
  return Number(await handle.getAttribute("aria-valuenow"));
}

/** What the inspector says of the selected plant. */
function properties(page: Page): Promise<string[]> {
  return page.locator('[data-testid^="property-"]').allTextContents();
}

test("renderer-smoke: the renderer, end to end", async ({ page }) => {
  test.setTimeout(WALKTHROUGH_TIMEOUT_MS);
  const transport = page.locator(".replay-transport");
  const handle = page.getByRole("slider", { name: "Position in the run" });
  const camera = page.getByTestId("camera-position");
  const run = await askForRun(page, SCENARIO, { seed: 65 });

  await test.step("Python computes a scenario's run, and its replay plays it", async () => {
    await computedTo(page, run, RUN_END_S, WALKTHROUGH_TIMEOUT_MS / 2);
    await openReplay(page, run);
    await transport.getByLabel("Pace").selectOption(QUICK);
    await transport.getByRole("button", { name: "Play" }).click();
    await expect(transport.getByRole("button", { name: "Pause" })).toBeVisible();
    await expect.poll(() => reached(page), ARRIVES).toBeGreaterThan(0);
  });

  await test.step("each camera preset moves the camera to its pose", async () => {
    for (const preset of PRESET_ORDER) {
      await page.getByRole("button", { name: PRESET_LABELS[preset], exact: true }).click();
      await expect(camera).toHaveText(formatPoint(CAMERA_PRESETS[preset].position));
    }
  });

  await test.step("paused, the replay holds; moved to its start, it is there", async () => {
    await transport.getByRole("button", { name: "Pause" }).click();
    await expect(transport.getByRole("button", { name: "Play" })).toBeVisible();
    // The climate field of the run's start, which the view asks for again: until
    // it arrives, the scene keeps the moment before's, its arrows among them,
    // and the overlays' count below would see them change under it.
    const fieldAtStart = page.waitForResponse(
      (response) =>
        /\/fields\/climate\?/.test(response.url()) &&
        !new URL(response.url()).searchParams.has("t"),
      ARRIVES,
    );
    await handle.focus();
    await page.keyboard.press("Home");
    await expect(handle).toHaveAttribute("aria-valuetext", "Day 1, 00:00");
    // Long enough for the replay to have asked where its position stands twice.
    await page.waitForTimeout(2500);
    expect(await reached(page)).toBe(0);
    await fieldAtStart;
    await expect.poll(() => steadyObjectCount(page), ARRIVES).toBeGreaterThan(0);
  });

  let shownPaused: string[] = [];
  await test.step("a plant is selected, and the inspector follows it", async () => {
    await selectAt(page, PLANT_POINT, PLANT);
    await expect(page.getByTestId("selected-position")).toHaveText("x 2.25, y 2.40, z 0.67");
    shownPaused = await properties(page);
    expect(shownPaused.length).toBeGreaterThan(0);
  });

  await test.step("overlay boxes and arrows are drawn around it, and can be switched off", async () => {
    const overlays = page.getByRole("group", { name: "Overlays" });
    // Its label, beside those of the scenario's weather, such as the sun.
    await expect(page.getByTestId("debug-label").filter({ hasText: PLANT })).toHaveCount(1);
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

  await test.step("drawn again at the moment it holds, the run shows the same plant", async () => {
    await page.reload();
    await expect(handle).toHaveAttribute("aria-valuetext", "Day 1, 00:00", ARRIVES);
    // Reloaded, the replay frames the house again.
    await page.getByRole("button", { name: "Isometric" }).click();
    await selectAt(page, PLANT_POINT, PLANT);
    expect(await properties(page)).toEqual(shownPaused);
  });

  await test.step("playing again, the replay moves it on, and the selection stays", async () => {
    await transport.getByLabel("Pace").selectOption(QUICK);
    await transport.getByRole("button", { name: "Play" }).click();
    await expect.poll(() => reached(page), ARRIVES).toBeGreaterThan(0);
    await expect(page.getByTestId("selected-entity")).toHaveText(PLANT);
    await stopRun(page, run);
  });

  await test.step("the screenshot baseline's page draws its seeded scene", async () => {
    await page.goto(`${QA_RENDERER_PATH}?seed=${DEFAULT_QA_SEED}`);
    await expect(page.getByTestId("debug-label")).toHaveText(QA_SELECTED_ID);
  });

  await test.step("the stress scene stays interactive", async () => {
    await page.goto(VIEWER_PATH);
    await (await chooser(page)).getByRole("button", { name: "Stress scene" }).click();
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
