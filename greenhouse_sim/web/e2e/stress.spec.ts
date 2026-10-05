import { expect, test } from "@playwright/test";

import { PLANTS_PER_ROW, stressPlantId, stressPlantPosition } from "../src/qa/stressScene.ts";
import { selectAt } from "./view";

// Enough plants to need instancing, few enough for CI's software renderer.
const PLANTS = 2_000;
const ROWS = PLANTS / PLANTS_PER_ROW;
// A plant near the middle of the field, in the row nearest the camera's side of it.
const COLUMN = 50;
const ROW = ROWS / 2;

test("thousands of plants are drawn in a handful of draw calls, and each can be picked", async ({
  page,
}) => {
  await page.goto(`/?scene=stress&plants=${PLANTS}`);

  await expect(page.getByTestId("scene-status")).toHaveText(
    `Showing the stress scene of ${PLANTS} plants: stress, day 0, ${PLANTS + 2} entities.`,
  );
  // One batch draws every plant: the draw calls stay in single figures.
  await expect(page.getByTestId("draw-calls")).toHaveText(/^\d \(\d{1,3}(,\d{3})* triangles\)$/);
  await expect(page.getByTestId("frame-time")).toHaveText(/^\d+\.\d ms, worst \d+\.\d ms$/);
  await expect(page.getByTestId("memory")).toHaveText(/^\d+ geometries, \d+ textures/);

  const plant = stressPlantPosition(COLUMN, ROW, ROWS);
  await selectAt(page, { ...plant, z: 0.15 }, stressPlantId(ROW * PLANTS_PER_ROW + COLUMN + 1));
  await expect(page.getByTestId("selected-position")).toHaveText(
    `x ${plant.x.toFixed(2)}, y ${plant.y.toFixed(2)}, z 0.00`,
  );
});
