import { expect, type Request, test } from "@playwright/test";

import { simulatedDay } from "./hud";
import { clickAt, clickSky, onScreen, selectAt } from "./view";

// The climate box's first plant stands on its gutter's slab, 0.675 m up.
// Clicked halfway up its stem in the example scene, and low on it in live
// scenes, where young plants are shorter.
const EXAMPLE_PLANT = { x: 2.25, y: 2.4, z: 0.85 };
const LIVE_PLANT = { x: 2.25, y: 2.4, z: 0.775 };
// The compartment's first plant, low on its stem above its gutter's slab.
const STILL_PLANT = { x: 2.75, y: 2.4, z: 0.775 };
// A point on the example scene's floor, between its right side wall and its
// first row, clear of the plants and the path across its front.
const EXAMPLE_FLOOR = { x: 3.0, y: 1.2, z: 0 };
// live.spec.ts and controls.spec.ts drive climate_box and airflow_box; this
// file pauses tomato_compartment, which no other test plays.
const STILL_SCENARIO = "tomato_compartment";

test("clicking an entity selects it, and the inspector shows what it is and where", async ({
  page,
}) => {
  await page.goto("/?scene=example");
  await expect(page.getByTestId("scene-status")).toContainText("127 entities");
  const selected = page.getByTestId("selected-entity");

  await selectAt(page, EXAMPLE_PLANT, "climate_box_plant_001");
  await expect(page.getByTestId("selected-position")).toHaveText("x 2.25, y 2.40, z 0.67");
  await expect(page.getByTestId("selected-rotation")).toHaveText(
    "w 1.000, x 0.000, y 0.000, z 0.000",
  );
  await expect(page.getByTestId("selected-shape")).toHaveText(
    "cylinder, radius 0.02 m, height 0.35 m",
  );
  await expect(page.getByTestId("debug-label")).toHaveText("climate_box_plant_001");

  // A drag orbits the camera and leaves the selection alone.
  const start = await onScreen(page, EXAMPLE_FLOOR);
  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  await page.mouse.move(start.x + 120, start.y + 40, { steps: 8 });
  await page.mouse.up();
  await expect(selected).toHaveText("climate_box_plant_001");

  await page.getByRole("button", { name: "Isometric" }).click();
  await clickAt(page, EXAMPLE_FLOOR);
  await expect(selected).toHaveText("climate_box_floor");

  // Clicking the sky selects nothing.
  await clickSky(page);
  await expect(page.getByRole("region", { name: "Inspector" })).toHaveCount(0);
  await expect(page.getByTestId("debug-label")).toHaveCount(0);
});

test("a selection stays on its entity while the live scenario plays", async ({ page }) => {
  await page.goto("/?live=climate_box");
  await expect(page.getByTestId("stream-status")).toHaveText("live");
  await expect.poll(() => simulatedDay(page)).toBeGreaterThanOrEqual(0);

  await selectAt(page, LIVE_PLANT, "climate_box_plant_001");
  const selected = page.getByTestId("selected-entity");
  const age = page.getByTestId("property-age_days");
  const firstAge = await age.textContent();

  // Each new day is a new scene; the selection and its label follow the plant.
  await expect(age).not.toHaveText(firstAge ?? "");
  await expect(selected).toHaveText("climate_box_plant_001");
  await expect(page.getByTestId("selected-position")).toHaveText("x 2.25, y 2.40, z 0.67");
  await expect(page.getByTestId("debug-label")).toHaveText("climate_box_plant_001");
});

test("overlays and colours change the view, never the simulation", async ({ page }) => {
  const live = `/api/scenarios/${STILL_SCENARIO}/live`;
  await page.request.post(`${live}/pause`);
  await page.request.post(`${live}/reset`);
  await page.goto(`/?live=${STILL_SCENARIO}`);
  await expect(page.getByTestId("stream-status")).toHaveText("live");
  await expect.poll(() => simulatedDay(page)).toBe(0);
  await selectAt(page, STILL_PLANT, "tomato_compartment_plant_001");
  const status = await page.getByTestId("scene-status").textContent();

  const requests: Request[] = [];
  page.on("request", (request) => requests.push(request));
  const overlays = page.getByRole("group", { name: "Overlays" });
  for (const overlay of ["Bounding box", "Origin and axes", "Label"]) {
    await overlays.getByLabel(overlay).uncheck();
  }
  await expect(page.getByTestId("debug-label")).toHaveCount(0);
  for (const overlay of ["Bounding box", "Origin and axes", "Label"]) {
    await overlays.getByLabel(overlay).check();
  }
  await expect(page.getByTestId("debug-label")).toHaveText("tomato_compartment_plant_001");

  const colourBy = page.getByLabel("Colour by");
  await colourBy.selectOption("visible_height_cm");
  await expect(page.getByTestId("legend-property")).toHaveText("visible_height_cm");
  await colourBy.selectOption("");
  await expect(page.getByRole("figure", { name: "Legend" })).toHaveCount(0);

  expect(requests.map((request) => request.url())).toEqual([]);
  expect(await simulatedDay(page)).toBe(0);
  await expect(page.getByTestId("scene-status")).toHaveText(status ?? "");
  await expect(page.getByTestId("selected-entity")).toHaveText("tomato_compartment_plant_001");
});
