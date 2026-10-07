import { expect, type Page, test } from "@playwright/test";

import { PLANT_LAB_LAST_DAY, PLANT_LAB_POSE } from "../src/plants/lab.ts";
import type { SceneSnapshot } from "../src/scene/generated/snapshotTypes.ts";
import type { Point3 } from "../src/world.ts";
import { selectAt } from "./view";

// The lab's row is thousands of entities, which CI's software renderer draws
// slowly: its tests have three times the usual time.
test.beforeEach(() => {
  test.slow();
});

// The plant, its stem, and per phytomer the phytomer, its internode and its
// leaf: the lab's plants bear no trusses yet.
const ORGANS_BESIDE_PHYTOMERS = 2;
const ORGANS_PER_PHYTOMER = 3;

/** The lab's row on a day, from a seed, as the simulator draws it. */
async function labScene(page: Page, day: number, seed = 1): Promise<SceneSnapshot> {
  const response = await page.request.get(`/api/plants/scene?day=${day}&seed=${seed}`);
  return response.json();
}

/** How many organs one of the lab's plants has on a day, from the simulator. */
async function organCount(page: Page, plantId: string, day: number, seed = 1): Promise<number> {
  const response = await page.request.get(
    `/api/plants/structure?day=${day}&seed=${seed}&plant=${plantId}`,
  );
  const plant = await response.json();
  return ORGANS_BESIDE_PHYTOMERS + plant.stem.phytomers.length * ORGANS_PER_PHYTOMER;
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

test("the slider runs as far as the simulator's lab does, and no further", async ({ page }) => {
  const last = await page.request.get(`/api/plants/scene?day=${PLANT_LAB_LAST_DAY}`);
  const beyond = await page.request.get(`/api/plants/scene?day=${PLANT_LAB_LAST_DAY + 1}`);

  expect(last.status()).toBe(200);
  expect(beyond.status()).toBe(400);
});
