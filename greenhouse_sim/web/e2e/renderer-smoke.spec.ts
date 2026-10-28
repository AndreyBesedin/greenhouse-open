import { expect, type Page, test } from "@playwright/test";
import { CAMERA_PRESETS, PRESET_ORDER, type PresetName } from "../src/camera.ts";
import { DAY_S } from "../src/clock.ts";
import { DEFAULT_QA_SEED, QA_RENDERER_PATH, QA_SELECTED_ID } from "../src/qa/qaPage.ts";
import {
  DEFAULT_STRESS_PLANTS,
  PLANTS_PER_ROW,
  stressPlantId,
  stressPlantPosition,
} from "../src/qa/stressScene.ts";
import { formatPoint } from "../src/readouts.ts";
import { chooser } from "./chooser";
import { selectAt } from "./view";

/**
 * P00's final QA, `renderer-smoke`: one walk through everything the renderer
 * does, as a person would use it. It runs as its own project once every other
 * browser test has passed (playwright.config.ts), so it can drive a scenario's
 * run played back, which every viewer shares, without disturbing them. The
 * screenshot itself is compared in CI's visual checks job, in its pinned
 * container.
 */

const SCENARIO = "climate_box";
const PLAYBACK = `/api/scenarios/${SCENARIO}/playback`;
const PLANT = "climate_box_plant_001";
// Low on the plant's stem, which is at least 20 cm tall on any day, above its
// gutter's slab.
const PLANT_POINT = { x: 2.25, y: 2.4, z: 0.775 };
// The climate box's run: 14 days, each played in 10 s.
const RUN_END_S = 14 * DAY_S;
const ARRIVES = { timeout: 60_000 };
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
// A walk through every feature, with a run played back a day in 10 s.
const WALKTHROUGH_TIMEOUT_MS = 180_000;
const DRAG_PX = { x: 160, y: 40 };

async function objectCount(page: Page): Promise<number> {
  return Number(await page.getByTestId("object-count").textContent());
}

/** Where the run's clock stands, as the playback panel's progress says. */
async function reached(page: Page): Promise<number> {
  const progress = page.getByRole("progressbar", { name: "The run's progress" });
  return Number(await progress.getAttribute("value"));
}

/** What the inspector says of the selected plant. */
function properties(page: Page): Promise<string[]> {
  return page.locator('[data-testid^="property-"]').allTextContents();
}

test("renderer-smoke: the renderer, end to end", async ({ page }) => {
  test.setTimeout(WALKTHROUGH_TIMEOUT_MS);
  const panel = page.getByRole("region", { name: "Run played back" });
  const status = panel.getByTestId("playback-status");
  const camera = page.getByTestId("camera-position");

  await test.step("Python plays a scenario's run back, and the view follows its clock", async () => {
    // Played back and playing, started over if its clock is too near the
    // run's end to be seen moving on, as after the other browser tests.
    const started = (await (await page.request.post(`${PLAYBACK}/start`)).json()) as {
      time_s: number;
      playing: boolean;
    };
    if (started.time_s > RUN_END_S - 4 * DAY_S) {
      expect((await page.request.post(`${PLAYBACK}/restart`)).ok()).toBe(true);
    } else if (!started.playing) {
      expect((await page.request.post(`${PLAYBACK}/play`)).ok()).toBe(true);
    }
    await page.goto(`/?scenario=${SCENARIO}&follow=1`);
    await expect(status).toContainText("playing a day in", ARRIVES);
    const first = await reached(page);
    await expect.poll(() => reached(page), ARRIVES).toBeGreaterThan(first);
  });

  await test.step("each camera preset moves the camera to its pose", async () => {
    for (const preset of PRESET_ORDER) {
      // Exactly: a followed view has "Stop following" beside "Top".
      await page.getByRole("button", { name: PRESET_LABELS[preset], exact: true }).click();
      await expect(camera).toHaveText(formatPoint(CAMERA_PRESETS[preset].position));
    }
  });

  await test.step("started over, the run's clock goes back to its start; paused, it holds", async () => {
    const before = await reached(page);
    await panel.getByRole("button", { name: "Start over" }).click();
    await expect.poll(() => reached(page), ARRIVES).toBeLessThan(before);
    await panel.getByRole("button", { name: "Pause" }).click();
    await expect(status).toContainText("paused");
    await expect(panel.getByRole("button", { name: "Play" })).toBeVisible();
    const held = await reached(page);
    // Long enough for the view to have asked where the clock stands twice.
    await page.waitForTimeout(2500);
    expect(await reached(page)).toBe(held);
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
    await expect(status).toContainText("paused", ARRIVES);
    // Reloaded, the followed view frames the house again.
    await page.getByRole("button", { name: "Isometric" }).click();
    await selectAt(page, PLANT_POINT, PLANT);
    expect(await properties(page)).toEqual(shownPaused);
  });

  await test.step("playing again, Python moves it on, and the selection stays", async () => {
    const held = await reached(page);
    await panel.getByRole("button", { name: "Play" }).click();
    await expect(status).toContainText("playing a day in");
    await expect.poll(() => reached(page), ARRIVES).toBeGreaterThan(held);
    await expect(page.getByTestId("selected-entity")).toHaveText(PLANT);
  });

  await test.step("the screenshot baseline's page draws its seeded scene", async () => {
    await page.goto(`${QA_RENDERER_PATH}?seed=${DEFAULT_QA_SEED}`);
    await expect(page.getByTestId("debug-label")).toHaveText(QA_SELECTED_ID);
  });

  await test.step("the stress scene stays interactive", async () => {
    await page.goto("/");
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
