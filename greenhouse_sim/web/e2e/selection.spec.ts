import { expect, type Request, test } from "@playwright/test";
import { DAY_S } from "../src/clock.ts";
import { unfold } from "./folds";
import { askForRun, computedTo, openReplay } from "./replays";
import { clickAt, clickSky, onScreen, selectAt } from "./view";

// The climate box's first plant stands on its gutter's slab, 0.675 m up.
// Clicked halfway up its stem in the example scene.
const EXAMPLE_PLANT = { x: 2.25, y: 2.4, z: 0.83 };
// A plant of the solar lab's row, on its gutter's slab too, low on its stem,
// where its young plants are shorter: the sixth, which its crates hide from
// none of the camera's presets, as they hide the first. Its run is replayed.
const REPLAYED_SCENARIO = "solar_lab";
const REPLAYED_PLANT_ID = "solar_lab_plant_006";
const REPLAYED_PLANT = { x: 4.75, y: 3.2, z: 0.775 };
// The days of its run computed before it is played: enough to see a day pass.
const DAYS_COMPUTED = 3;
const ARRIVES = { timeout: 60_000 };
// The compartment's first plant, low on its stem above its gutter's slab.
const STILL_PLANT = { x: 2.75, y: 2.4, z: 0.775 };
// A point on the example scene's floor, between its right side wall and its
// first row, clear of the plants and the path across its front.
const EXAMPLE_FLOOR = { x: 3.0, y: 1.2, z: 0 };
// A scenario's run drawn at its start, not followed: nothing moves it on.
const STILL_SCENARIO = "tomato_compartment";

test("clicking an entity selects it, and the inspector shows what it is and where", async ({
  page,
}) => {
  await page.goto("/?scene=example");
  await expect(page.getByTestId("scene-status")).toContainText("128 entities");
  const selected = page.getByTestId("selected-entity");

  await selectAt(page, EXAMPLE_PLANT, "climate_box_plant_001");
  await expect(page.getByTestId("selected-position")).toHaveText("x 2.25, y 2.40, z 0.67");
  await expect(page.getByTestId("selected-rotation")).toHaveText(
    "w 1.000, x 0.000, y 0.000, z 0.000",
  );
  await expect(page.getByTestId("selected-shape")).toHaveText(
    "cylinder, radius 0.02 m, height 0.31 m",
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

test("a selection stays on its entity while the replay plays its run on", async ({ page }) => {
  test.slow();
  const run = await askForRun(page, REPLAYED_SCENARIO, { seed: 64 });
  await computedTo(page, run, DAYS_COMPUTED * DAY_S, 120_000);
  await openReplay(page, run);

  // A replay frames the whole house; the plant is aimed at from the default
  // preset.
  await page.getByRole("button", { name: "Isometric" }).click();
  await selectAt(page, REPLAYED_PLANT, REPLAYED_PLANT_ID);
  const selected = page.getByTestId("selected-entity");
  const age = page.getByTestId("property-age_days");
  const firstAge = await age.textContent();

  // Played at its quickest, each new day of the crop is a new scene; the
  // selection and its label follow the plant.
  const transport = page.locator(".replay-transport");
  await transport.getByLabel("Pace").selectOption("2");
  await transport.getByRole("button", { name: "Play" }).click();
  await expect(age).not.toHaveText(firstAge ?? "", ARRIVES);
  await expect(selected).toHaveText(REPLAYED_PLANT_ID);
  await expect(page.getByTestId("selected-position")).toHaveText("x 4.75, y 3.20, z 0.67");
  // A scenario's view labels its weather too, such as the sun.
  await expect(page.getByTestId("debug-label").filter({ hasText: REPLAYED_PLANT_ID })).toHaveCount(
    1,
  );
});

test("overlays and colours change the view, never the simulation", async ({ page }) => {
  // On CI's software renderer the compartment draws a few frames a second,
  // and each of the six switches below waits several of them: they took 28
  // of the default 30 s on a slow runner, before the colouring's section
  // was even opened.
  test.slow();
  await page.goto(`/?scenario=${STILL_SCENARIO}`);
  await expect(page.getByTestId("scene-status")).toContainText("entities", ARRIVES);
  await selectAt(page, STILL_PLANT, "tomato_compartment_plant_001");
  const status = await page.getByTestId("scene-status").textContent();
  // The plant's label, beside those of the scenario's weather, such as the sun.
  const label = page.getByTestId("debug-label").filter({ hasText: "tomato_compartment_plant_001" });

  const requests: Request[] = [];
  page.on("request", (request) => requests.push(request));
  const overlays = page.getByRole("group", { name: "Overlays" });
  for (const overlay of ["Bounding box", "Origin and axes", "Label"]) {
    await overlays.getByLabel(overlay).uncheck();
  }
  await expect(label).toHaveCount(0);
  for (const overlay of ["Bounding box", "Origin and axes", "Label"]) {
    await overlays.getByLabel(overlay).check();
  }
  await expect(label).toHaveCount(1);

  const colourBy = page.getByLabel("Colour by");
  await unfold(page, "Display");
  await colourBy.selectOption("visible_height_cm");
  await expect(page.getByTestId("legend-property")).toHaveText("visible_height_cm");
  await colourBy.selectOption("");
  await expect(page.getByRole("figure", { name: "Legend" })).toHaveCount(0);

  expect(requests.map((request) => request.url())).toEqual([]);
  await expect(page.getByTestId("scene-status")).toHaveText(status ?? "");
  await expect(page.getByTestId("selected-entity")).toHaveText("tomato_compartment_plant_001");
});
