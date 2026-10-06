import { expect, test } from "@playwright/test";

import { QA_LAYOUT_PATH } from "../src/qa/layoutViews.ts";
import { selectAt } from "./view";

// P02's final QA, `greenhouse-layout`, in the browser: two layouts of one
// scenario inspected, the plants' spacing measured, the walkways seen clear,
// rails and pipes inspected from inside the rows, and every part selected as
// what it is. The screenshots are compared by CI's visual checks job, and the
// same promises are checked over many layouts in
// `tests/test_greenhouse_layout.py`.

// gh_001's rows: four rows of ten, 0.5 m apart along a row and 1.6 m from
// row to row, the first at (1.75, 2.4); on gutters with slabs, the plants
// stand at 0.675 m; on benches, at 0.8 m.
const SLAB_TOP_M = 0.675;
const BENCH_TOP_M = 0.8;
const LOW_ON_A_STEM_M = 0.1;
const FRONT_AISLE = { x: 0.7, y: 4.0, z: 0.02 };
const FIRST_GUTTER_SIDE = { x: 3.0, y: 2.4 - 0.15, z: 0.54 };
const TUBE_RADIUS_M = 0.0255;
// Picked from above: from the side, the gutters hide the rails.
const RAIL_TUBE_TOP = { x: 3.1, y: 3.2 + 0.275, z: 0.1 + TUBE_RADIUS_M };
const TOP_HEATING_PIPE = { x: 3.0, y: 0.25, z: 0.75 + TUBE_RADIUS_M };

test("greenhouse-layout: two layouts inspected, measured, clear and selected by what they are", async ({
  page,
}) => {
  // Six scene loads and a dozen picks: slow where the browser draws in
  // software, as in CI.
  test.slow();
  const status = page.getByTestId("scene-status");
  const position = page.getByTestId("selected-position");
  const type = page.getByTestId("selected-type");
  const dimensions = page.getByTestId("selected-dimensions");
  const inspector = page.getByRole("region", { name: "Inspector" });

  // The default layout: gutters, aisles, zones, rails, pipes and wires, its
  // hundred and more cylinders drawn in a few instanced batches.
  await page.goto("/?scenario=gh_001");
  await expect(status).toContainText("gh_001, day 0, 165 entities");
  await expect(page.getByTestId("draw-calls")).toHaveText(/^\d{2} \(/);
  await page.getByRole("checkbox", { name: "Categories" }).check();
  await expect(page.getByTestId("layout-category")).toHaveCount(10);
  await page.getByRole("checkbox", { name: "Categories" }).uncheck();

  // Selected as what it is: a gutter, and a walkway that obstructs nothing,
  // so walking it is never blocked.
  await selectAt(page, FIRST_GUTTER_SIDE, "gh_001_row_1_support_1");
  await expect(type).toHaveText("crop gutter");
  await expect(dimensions).toHaveText("length 5.00 m, width 0.30 m, height 0.12 m");
  await selectAt(page, FRONT_AISLE, "gh_001_front_aisle");
  await expect(type).toHaveText("walkway");
  await expect(page.getByTestId("property-obstructs_movement")).toHaveText("false");

  // The spacing, measured from the plants' coordinates on their slabs.
  const z = (top: number) => ({ z: top + LOW_ON_A_STEM_M });
  await selectAt(page, { x: 1.75, y: 2.4, ...z(SLAB_TOP_M) }, "gh_001_plant_001");
  await expect(position).toHaveText("x 1.75, y 2.40, z 0.67");
  await selectAt(page, { x: 2.25, y: 2.4, ...z(SLAB_TOP_M) }, "gh_001_plant_002");
  await expect(position).toHaveText("x 2.25, y 2.40, z 0.67");
  await selectAt(page, { x: 1.75, y: 4.0, ...z(SLAB_TOP_M) }, "gh_001_plant_011");
  await expect(position).toHaveText("x 1.75, y 4.00, z 0.67");
  await inspector.getByRole("button", { name: "Clear selection" }).click();

  // Rails and pipes, from above the rows.
  await page.getByRole("button", { name: "Top" }).click();
  await selectAt(page, RAIL_TUBE_TOP, "gh_001_rail_1_1_left", "top");
  await expect(type).toHaveText("rail");
  await selectAt(page, TOP_HEATING_PIPE, "gh_001_heating_pipes_right_4", "top");
  await expect(type).toHaveText("pipe");
  await expect(dimensions).toHaveText("diameter 0.05 m, length 6.50 m");
  await inspector.getByRole("button", { name: "Clear selection" }).click();

  // The second layout: the same rows on benches, the same spacing.
  await page.getByRole("button", { name: "Isometric" }).click();
  await page.getByRole("combobox", { name: "Layout of gh_001" }).selectOption("benches");
  await expect(status).toContainText("benches layout, before day one: gh_001, day 0, 155");
  await selectAt(page, { x: 2.25, y: 2.4, ...z(BENCH_TOP_M) }, "gh_001_plant_002");
  await expect(position).toHaveText("x 2.25, y 2.40, z 0.80");
  await selectAt(page, { x: 3.0, y: 1.9, z: BENCH_TOP_M }, "gh_001_row_1_support_1");
  await expect(type).toHaveText("bench");

  // Its layout, written out by the simulator as its file holds it: data,
  // with its walkways and zones.
  const layout = await (
    await page.request.get("/api/scenarios/gh_001/layout?layout=benches")
  ).json();
  expect(layout.crop_rows.support.kind).toBe("bench");
  expect(layout.placed.map((placed: { fixture_id: string }) => placed.fixture_id)).toContain(
    "front_aisle",
  );
  expect(layout.zones).toHaveLength(2);

  // Inside the rows of the canonical layout, riding a rail.
  await page.goto(`${QA_LAYOUT_PATH}?view=between-rows`);
  await expect(page.getByTestId("qa-caption")).toHaveText("Layout QA, between-rows view");
});
