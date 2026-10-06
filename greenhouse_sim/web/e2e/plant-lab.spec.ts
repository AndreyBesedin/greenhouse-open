import { expect, test } from "@playwright/test";

import { PLANT_LAB_POSE } from "../src/plants/lab.ts";
import { selectAt } from "./view";

// The plant lab's reference young plant: nine phytomers, the lower ones' internodes
// 6 cm long, its first truss on the ninth with six flower buds, standing at the
// origin. Each leaf is a petiole, three rachis segments and seven leaflets.
const INTERNODE_M = 0.06;
const LEAF_PARTS = 1 + 3 + 7;
// Halfway up the third internode.
const THIRD_INTERNODE = { x: 0, y: 0, z: 2.5 * INTERNODE_M };

test("the plant lab draws a young plant from its structure, organ by organ", async ({ page }) => {
  await page.goto("/?plants=lab");
  // The ground and axes, then nine internodes and leaves, a truss and its flowers.
  const entities = 2 + 9 * (1 + LEAF_PARTS) + 1 + 6;
  await expect(page.getByTestId("scene-status")).toHaveText(
    `Showing the plant lab: plant_lab, day 0, ${entities} entities.`,
  );

  // The debug tree: the plant, its stem, nine phytomers of an internode and a
  // leaf each, and the truss with its six flowers.
  const organs = page.getByTestId("organ");
  await expect(organs).toHaveCount(2 + 9 * 3 + 1 + 6);
  await expect(page.locator('[data-organ-kind="flower"]')).toHaveCount(6);

  // An organ chosen in the tree is selected in the view, by its first part.
  const leaf = page.getByRole("button", { name: "p01_n04_leaf" });
  await leaf.click();
  await expect(page.getByTestId("selected-entity")).toHaveText("p01_n04_leaf_petiole");
  await expect(page.getByTestId("property-organ_id")).toHaveText("p01_n04_leaf");
  await expect(page.getByTestId("property-parent_id")).toHaveText("p01_n04");
  await expect(page.getByTestId("property-part")).toHaveText("petiole");
  await expect(leaf).toHaveAttribute("aria-pressed", "true");

  // And an organ clicked in the view is the organ the tree names.
  await page.getByRole("button", { name: "Clear selection" }).click();
  await selectAt(page, THIRD_INTERNODE, "p01_n03_internode", PLANT_LAB_POSE);
  await expect(page.getByTestId("property-thermal_age_cd")).toHaveText("198");
  await expect(page.getByRole("button", { name: "p01_n03_internode" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(leaf).toHaveAttribute("aria-pressed", "false");
});
