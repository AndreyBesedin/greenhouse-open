import { expect as baseExpect, type Page, test } from "@playwright/test";

import { PLANT_LAB_LAST_DAY, PLANT_LAB_POSE } from "../src/plants/lab.ts";
import type { SceneSnapshot } from "../src/scene/generated/snapshotTypes.ts";
import type { Point3 } from "../src/world.ts";
import { selectAt } from "./view";

// The lab's row is thousands of entities, which the simulator takes a while
// to grow on its later days and CI's software renderer to draw: its tests have
// three times the usual time, and wait this long for what they expect.
const LAB_EXPECT_TIMEOUT_MS = 30_000;
const expect = baseExpect.configure({ timeout: LAB_EXPECT_TIMEOUT_MS });
test.beforeEach(() => {
  test.slow();
});

interface StructureFruit {
  fruit_id: string;
  stage: string;
  ripeness: number;
}

interface Structure {
  stem: {
    phytomers: {
      truss: { flowers: { flower_id: string; fruit: StructureFruit | null }[] } | null;
    }[];
  };
}

/** One of the lab's plants on a day, as the simulator describes it. */
async function labPlant(page: Page, plantId: string, day: number, seed = 1): Promise<Structure> {
  const response = await page.request.get(
    `/api/plants/structure?day=${day}&seed=${seed}&plant=${plantId}`,
  );
  return response.json();
}

/** How many organs a plant has: itself and its stem, each phytomer with its
 * internode and leaf, and each truss with its flowers and their fruits. */
function organsOf(plant: Structure): number {
  return plant.stem.phytomers.reduce((count, { truss }) => {
    const flowers = truss?.flowers ?? [];
    const fruits = flowers.filter((flower) => flower.fruit !== null).length;
    return count + 3 + (truss === null ? 0 : 1 + flowers.length + fruits);
  }, 2);
}

/** The lab's row on a day, from a seed, as the simulator draws it, in more
 * than its reference environment if `environments` says. */
async function labScene(
  page: Page,
  day: number,
  seed = 1,
  environments = "",
): Promise<SceneSnapshot> {
  const response = await page.request.get(
    `/api/plants/scene?day=${day}&seed=${seed}${environments}`,
  );
  return response.json();
}

/** How many organs one of the lab's plants has on a day, from the simulator. */
async function organCount(page: Page, plantId: string, day: number, seed = 1): Promise<number> {
  return organsOf(await labPlant(page, plantId, day, seed));
}

function centreOf(scene: SceneSnapshot, entityId: string): Point3 {
  const entity = scene.entities.find((candidate) => candidate.entity_id === entityId);
  if (entity === undefined) {
    throw new Error(`the lab draws no ${entityId}`);
  }
  return entity.transform.position;
}

test("the plant lab draws its row from its plants' structure, organ by organ", async ({ page }) => {
  const scene = await labScene(page, 0);
  await page.goto("/?plants=lab");
  await expect(page.getByTestId("scene-status")).toHaveText(
    `Showing the plant lab: plant_lab, day 0, ${scene.entities.length} entities.`,
  );

  // The debug tree shows the row's first plant.
  await expect(page.getByText("Plant structure: p01")).toBeVisible();
  await expect(page.getByTestId("organ")).toHaveCount(await organCount(page, "p01", 0));
  await expect(page.locator('[data-organ-kind="truss"]')).toHaveCount(0);

  // An organ chosen in the tree is selected in the view, by its first part.
  const leaf = page.getByRole("button", { name: "p01_n04_leaf" });
  await leaf.click();
  await expect(page.getByTestId("selected-entity")).toHaveText("p01_n04_leaf_petiole");
  await expect(page.getByTestId("property-organ_id")).toHaveText("p01_n04_leaf");
  await expect(page.getByTestId("property-parent_id")).toHaveText("p01_n04");
  await expect(page.getByTestId("property-part")).toHaveText("petiole");
  await expect(leaf).toHaveAttribute("aria-pressed", "true");

  // And a part of an organ clicked in the view is the organ the tree names.
  await page.getByRole("button", { name: "Clear selection" }).click();
  const leaflet = "p01_n03_leaf_terminal";
  await selectAt(page, centreOf(scene, leaflet), leaflet, PLANT_LAB_POSE);
  await expect(page.getByTestId("property-thermal_age_cd")).toHaveText("161.40");
  await expect(page.getByRole("button", { name: "p01_n03_leaf" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(leaf).toHaveAttribute("aria-pressed", "false");
});

test("the row grows day by day, and an organ selected stays selected as it grows", async ({
  page,
}) => {
  const later = await labScene(page, 30);
  await page.goto("/?plants=lab");
  await expect(page.getByTestId("plant-day")).toHaveText("day 0");
  await page.getByRole("button", { name: "p01_n04_leaf" }).click();
  await expect(page.getByTestId("property-thermal_age_cd")).toHaveText("127.10");

  await page.getByRole("slider").fill("30");

  await expect(page.getByTestId("scene-status")).toHaveText(
    `Showing the plant lab: plant_lab, day 30, ${later.entities.length} entities.`,
  );
  await expect(page.getByTestId("plant-day")).toHaveText("day 30");
  await expect(page).toHaveURL(/\?plants=lab&day=30$/);
  await expect(page.getByTestId("organ")).toHaveCount(await organCount(page, "p01", 30));
  // The same leaf, thirty days of 11 °Cd older.
  await expect(page.getByTestId("selected-entity")).toHaveText("p01_n04_leaf_petiole");
  await expect(page.getByTestId("property-thermal_age_cd")).toHaveText("457.10");
  await expect(page.getByRole("button", { name: "p01_n04_leaf" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});

test("another seed draws another row, and the tree follows the plant selected", async ({
  page,
}) => {
  const first = await labScene(page, 20, 1);
  const second = await labScene(page, 20, 2);
  expect(second.entities).not.toEqual(first.entities);
  await page.goto("/?plants=lab&day=20");
  await expect(page.getByTestId("scene-status")).toContainText(`${first.entities.length} entities`);

  await page.getByRole("button", { name: "Another seed" }).click();

  await expect(page).toHaveURL(/\?plants=lab&day=20&seed=2$/);
  await expect(page.getByTestId("scene-status")).toHaveText(
    `Showing the plant lab: plant_lab, day 20, ${second.entities.length} entities.`,
  );
  // The third plant's leaflet, clicked in the view, brings its plant's tree.
  const leaflet = "p03_n02_leaf_terminal";
  await selectAt(page, centreOf(second, leaflet), leaflet, PLANT_LAB_POSE);
  await expect(page.getByText("Plant structure: p03")).toBeVisible();
  await expect(page.getByTestId("organ")).toHaveCount(await organCount(page, "p03", 20, 2));
  await expect(page.getByRole("button", { name: "p03_n02_leaf" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
});

test("a plant flowers and sets fruit, and a fruit is selected from the tree", async ({ page }) => {
  const plant = await labPlant(page, "p01", 45);
  const fruit = plant.stem.phytomers
    .flatMap(({ truss }) => truss?.flowers ?? [])
    .map((flower) => ({ flowerId: flower.flower_id, fruit: flower.fruit }))
    .find(({ fruit }) => fruit?.stage === "attached");
  if (fruit === undefined || fruit.fruit === null) {
    throw new Error("the lab's first plant has no fruit on day 45");
  }
  await page.goto("/?plants=lab&day=45");
  // The tree and the scene arrive separately; an organ is selected in the scene.
  await expect(page.getByTestId("scene-status")).toContainText("day 45");
  await expect(page.getByTestId("organ")).toHaveCount(organsOf(plant));
  await expect(page.locator('[data-organ-kind="truss"]').first()).toBeVisible();

  await page.getByRole("button", { name: fruit.fruit.fruit_id }).click();

  await expect(page.getByTestId("selected-entity")).toHaveText(fruit.fruit.fruit_id);
  await expect(page.getByTestId("property-organ_kind")).toHaveText("fruit");
  await expect(page.getByTestId("property-parent_id")).toHaveText(fruit.flowerId);
  await expect(page.getByTestId("property-stage")).toHaveText("attached");
  // A set flower is drawn as its fruit, so it is not a link of its own.
  await expect(page.getByRole("button", { name: fruit.flowerId, exact: true })).toHaveCount(0);
});

test("a fruit followed through the days grows and ripens from green to red", async ({ page }) => {
  // A fruit that is red by the end of the lab's run.
  const end = await labPlant(page, "p01", PLANT_LAB_LAST_DAY);
  const ripe = end.stem.phytomers
    .flatMap(({ truss }) => truss?.flowers ?? [])
    .map(({ fruit }) => fruit)
    .find((fruit) => fruit !== null && fruit.stage === "attached" && fruit.ripeness === 1);
  if (ripe === undefined || ripe === null) {
    throw new Error("the lab's first plant has no red fruit by the end of its run");
  }
  await page.goto("/?plants=lab&day=60");
  await expect(page.getByTestId("scene-status")).toContainText("day 60");
  await page.getByRole("button", { name: ripe.fruit_id }).click();
  await expect(page.getByTestId("property-maturity")).toHaveText("green");
  const green = Number(await page.getByTestId("property-mass_g").textContent());

  await page.getByRole("slider").fill(String(PLANT_LAB_LAST_DAY));

  await expect(page.getByTestId("scene-status")).toContainText(`day ${PLANT_LAB_LAST_DAY}`);
  await expect(page.getByTestId("selected-entity")).toHaveText(ripe.fruit_id);
  await expect(page.getByTestId("property-maturity")).toHaveText("red");
  await expect(page.getByTestId("property-ripeness")).toHaveText("1");
  const red = Number(await page.getByTestId("property-mass_g").textContent());
  expect(red).toBeGreaterThan(green);
});

test("two environments side by side: every second plant lives in the other", async ({ page }) => {
  const both = "&environment=cool_dim&versus=warm_bright";
  // Early in the run, while the plants are small enough not to hide each other.
  const scene = await labScene(page, 10, 1, both);
  await page.goto("/?plants=lab&day=10");
  await expect(page.getByTestId("lab-environment")).toHaveText(
    "21 °C, 25 mol/m²/d PAR, 800 ppm CO₂, water 100%",
  );

  await page.getByRole("combobox", { name: "Environment" }).selectOption("cool_dim");
  await page.getByRole("combobox", { name: "Beside it" }).selectOption("warm_bright");

  await expect(page).toHaveURL(/\?plants=lab&day=10&environment=cool_dim&versus=warm_bright$/);
  await expect(page.getByTestId("lab-versus")).toHaveText(
    "25 °C, 32 mol/m²/d PAR, 1000 ppm CO₂, water 100%",
  );
  await expect(page.getByTestId("scene-status")).toHaveText(
    `Showing the plant lab: plant_lab, day 10, ${scene.entities.length} entities.`,
  );
  // The row's second plant lives beside its first, in the other environment.
  for (const [plantId, environment] of [
    ["p02", "warm_bright"],
    ["p01", "cool_dim"],
  ]) {
    const leaflet = `${plantId}_n03_leaf_terminal`;
    await selectAt(page, centreOf(scene, leaflet), leaflet, PLANT_LAB_POSE);
    await expect(page.getByTestId("property-environment")).toHaveText(environment ?? "");
    await expect(page.getByText(`Plant structure: ${plantId}`)).toBeVisible();
  }
});

test("the slider runs as far as the simulator's lab does, and no further", async ({ page }) => {
  const last = await page.request.get(`/api/plants/scene?day=${PLANT_LAB_LAST_DAY}`);
  const beyond = await page.request.get(`/api/plants/scene?day=${PLANT_LAB_LAST_DAY + 1}`);

  expect(last.status()).toBe(200);
  expect(beyond.status()).toBe(400);
});
