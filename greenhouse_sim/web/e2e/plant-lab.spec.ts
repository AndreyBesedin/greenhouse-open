import { expect, type Page, test } from "@playwright/test";

import { PLANT_LAB_LAST_DAY, PLANT_LAB_POSE } from "../src/plants/lab.ts";
import type { SceneSnapshot } from "../src/scene/generated/snapshotTypes.ts";
import type { Point3 } from "../src/world.ts";
import { selectAt } from "./view";

// Each leaf is a petiole, three rachis segments and seven leaflets.
const LEAF_PARTS = 1 + 3 + 7;
// The ground and the axes.
const LAB_ENTITIES = 2;
// The plant lab's transplant has seven phytomers on day 0 and seventeen by
// day 30, each an internode and a leaf; it bears no trusses yet.
const PHYTOMERS_ON_DAY_0 = 7;
const PHYTOMERS_ON_DAY_30 = 17;

function entitiesWith(phytomers: number): number {
  return LAB_ENTITIES + phytomers * (1 + LEAF_PARTS);
}

/** Where the lab's scene on day 0 centres one of its entities. */
async function centreOf(page: Page, entityId: string): Promise<Point3> {
  const response = await page.request.get("/api/plants/scene?day=0");
  const scene: SceneSnapshot = await response.json();
  const entity = scene.entities.find((candidate) => candidate.entity_id === entityId);
  if (entity === undefined) {
    throw new Error(`the lab draws no ${entityId}`);
  }
  return entity.transform.position;
}

test("the plant lab draws its plant from its structure, organ by organ", async ({ page }) => {
  await page.goto("/?plants=lab");
  await expect(page.getByTestId("scene-status")).toHaveText(
    `Showing the plant lab: plant_lab, day 0, ${entitiesWith(PHYTOMERS_ON_DAY_0)} entities.`,
  );

  // The debug tree: the plant, its stem, and its phytomers of an internode
  // and a leaf each.
  const organs = page.getByTestId("organ");
  await expect(organs).toHaveCount(2 + PHYTOMERS_ON_DAY_0 * 3);
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
  await selectAt(page, await centreOf(page, leaflet), leaflet, PLANT_LAB_POSE);
  // Transplanted at 230 °Cd, the third phytomer appeared at 66 °Cd.
  await expect(page.getByTestId("property-thermal_age_cd")).toHaveText("164");
  await expect(page.getByRole("button", { name: "p01_n03_leaf" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(leaf).toHaveAttribute("aria-pressed", "false");
});

test("the plant grows day by day, and an organ selected stays selected as it grows", async ({
  page,
}) => {
  await page.goto("/?plants=lab");
  await expect(page.getByTestId("plant-day")).toHaveText("day 0");
  await page.getByRole("button", { name: "p01_n04_leaf" }).click();
  await expect(page.getByTestId("property-thermal_age_cd")).toHaveText("131");

  await page.getByRole("slider").fill("30");

  await expect(page.getByTestId("scene-status")).toHaveText(
    `Showing the plant lab: plant_lab, day 30, ${entitiesWith(PHYTOMERS_ON_DAY_30)} entities.`,
  );
  await expect(page.getByTestId("plant-day")).toHaveText("day 30");
  await expect(page).toHaveURL(/\?plants=lab&day=30$/);
  await expect(page.getByTestId("organ")).toHaveCount(2 + PHYTOMERS_ON_DAY_30 * 3);
  // The same leaf, thirty days of 11 °Cd older.
  await expect(page.getByTestId("selected-entity")).toHaveText("p01_n04_leaf_petiole");
  await expect(page.getByTestId("property-thermal_age_cd")).toHaveText("461");
  await expect(page.getByRole("button", { name: "p01_n04_leaf" })).toHaveAttribute(
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
