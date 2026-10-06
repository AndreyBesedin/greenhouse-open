import { expect, test } from "@playwright/test";

import { selectAt } from "./view";

// The fixture gallery (`tests/test_scene_schema.py`): one fixture of each
// primitive across an 8 by 4.8 m greenhouse centred on the world's origin,
// each picked from above at a point on its top, in the world.
const FIXTURES = [
  {
    id: "qa_fixtures_cabinet",
    top: { x: -2.8, y: 0, z: 1.8 },
    kind: "OBSTACLE",
    shape: "box, 0.60 × 1.20 × 1.80 m",
    material: "steel",
  },
  {
    id: "qa_fixtures_tank",
    top: { x: -1.6, y: 0, z: 1.5 },
    kind: "OBSTACLE",
    shape: "cylinder, radius 0.50 m, height 1.50 m",
    material: "plastic",
  },
  {
    id: "qa_fixtures_heating_pipe",
    top: { x: -0.6, y: 0, z: 0.6 },
    kind: "PIPE",
    shape: "cylinder, radius 0.03 m, height 3.65 m",
    material: "steel",
  },
  {
    id: "qa_fixtures_pipe_rail_right",
    top: { x: 0.775, y: 0, z: 0.1 },
    kind: "RAIL",
    shape: "cylinder, radius 0.03 m, height 3.60 m",
    material: "steel",
  },
  {
    id: "qa_fixtures_crop_gutter",
    top: { x: 1.6, y: 0, z: 0.12 },
    kind: "CROP_GUTTER",
    shape: "box, 3.60 × 0.30 × 0.12 m",
    material: "plastic",
  },
  {
    id: "qa_fixtures_walkway",
    top: { x: 2.8, y: 0, z: 0.02 },
    kind: "WALKWAY",
    shape: "box, 4.20 × 1.20 × 0.02 m",
    material: "concrete",
  },
] as const;

// Large enough that the panels around the view leave the gallery clear.
test.use({ viewport: { width: 1920, height: 1080 } });

test("the fixture gallery shows each primitive at its size, made of its material", async ({
  page,
}) => {
  await page.goto("/?scene=fixtures");
  await expect(page.getByTestId("scene-status")).toHaveText(
    "Showing the fixture gallery: qa_fixtures, day 0, 30 entities.",
  );
  await page.getByRole("button", { name: "Top" }).click();
  const inspector = page.getByRole("region", { name: "Inspector" });

  for (const fixture of FIXTURES) {
    await selectAt(page, fixture.top, fixture.id, "top");
    await expect(inspector.getByText(fixture.kind, { exact: true })).toBeVisible();
    await expect(page.getByTestId("selected-shape")).toHaveText(fixture.shape);
    await expect(page.getByTestId("selected-material")).toHaveText(fixture.material);
    if (fixture.kind === "WALKWAY") {
      // A walkway is walked on: it obstructs nothing.
      await expect(page.getByTestId("property-obstructs_movement")).toHaveText("false");
      await expect(page.getByTestId("property-obstructs_airflow")).toHaveText("false");
      await expect(page.getByTestId("property-obstructs_light")).toHaveText("false");
    }
    // The inspector covers the right of the view; clearing the selection
    // closes it, so the next fixture can be clicked.
    await inspector.getByRole("button", { name: "Clear selection" }).click();
  }
});
