import { expect, test } from "@playwright/test";

import { selectAt } from "./view";

// The compartment's crop rows: eight rows of forty planting positions along
// its length, 0.5 m apart along a row and 1.6 m from row to row, the first at
// (2.75, 2.4), each row on a tomato gutter whose slab's top is at 0.675 m.
// A plant stands at each, picked low on its stem at day 0.
const SLAB_TOP_M = 0.675;
const STEM_HEIGHT_M = SLAB_TOP_M + 0.1;
// A position's marker shows as a ring around the plant on it; this far from
// its centre, on the side the default camera looks from, the ring is clear
// of the stem.
const RING_M = 0.03;

test("planting positions can be counted and measured from their coordinates", async ({ page }) => {
  await page.goto("/?scenario=tomato_compartment");
  await expect(page.getByTestId("scene-status")).toContainText(
    "tomato_compartment, day 0, 896 entities",
  );
  const position = page.getByTestId("selected-position");
  const plantingPosition = page.getByTestId("property-planting_position");

  // Each plant stands at its planting position, whose coordinates the
  // inspector gives: 0.5 m along the row, 1.6 m to the next row.
  await selectAt(page, { x: 2.75, y: 2.4, z: STEM_HEIGHT_M }, "tomato_compartment_plant_001");
  await expect(plantingPosition).toHaveText("row_1_position_1");
  await expect(position).toHaveText("x 2.75, y 2.40, z 0.67");
  await selectAt(page, { x: 3.25, y: 2.4, z: STEM_HEIGHT_M }, "tomato_compartment_plant_002");
  await expect(plantingPosition).toHaveText("row_1_position_2");
  await expect(position).toHaveText("x 3.25, y 2.40, z 0.67");
  await selectAt(page, { x: 2.75, y: 4.0, z: STEM_HEIGHT_M }, "tomato_compartment_plant_041");
  await expect(plantingPosition).toHaveText("row_2_position_1");
  await expect(position).toHaveText("x 2.75, y 4.00, z 0.67");

  // The ring around a plant's foot is the planting position itself.
  const ring = { x: 2.75 + RING_M, y: 2.4 - RING_M, z: SLAB_TOP_M + 0.01 };
  await selectAt(page, ring, "tomato_compartment_row_1_position_1");
  await expect(page.getByTestId("property-row")).toHaveText("1");
  await expect(page.getByTestId("property-position_in_row")).toHaveText("1");

  // Coloured by their place, the positions count eight rows of forty.
  const colourBy = page.getByLabel("Colour by");
  for (const [property, last] of [
    ["row", "8"],
    ["position_in_row", "40"],
  ] as const) {
    await colourBy.selectOption(property);
    await expect(page.getByTestId("legend-min")).toHaveText("1");
    await expect(page.getByTestId("legend-max")).toHaveText(last);
  }
});
