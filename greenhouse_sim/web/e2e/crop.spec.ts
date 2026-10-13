import { expect, type Page, test } from "@playwright/test";

import type { CameraPose } from "../src/camera.ts";
import { clickAt } from "./view";

// The reference greenhouse's crop (P09.3): 32 transplants organ by organ,
// each living each day in the house's air and its own light. Its first
// plant stands at the start of its first row, on a gutter 0.675 m up,
// leaning out to the left wire, 0.3 m aside and 2.925 m above its foot; it
// is picked by its stem, 7.5 cm up, seen from along the row, nothing
// between.
const STEM = { x: 3.0, y: 2.4 + (0.075 * 0.3) / 2.925, z: 0.75 };
const ALONG_THE_ROW: CameraPose = { position: { x: 1.6, y: 2.4, z: 1.0 }, target: STEM };
const CAMERA = `1.6:2.4:1,3:${STEM.y}:0.75`;
const PLANT = "reference_greenhouse_plant_001";
const NOON_S = 43_200;
const DAY_S = 86_400;
// A later day's moment takes the simulator the house's air through the days
// before it, its field then, and the crop's days.
const ARRIVES = { timeout: 90_000 };

/** Clicks the first plant's stem until one of its organs is selected: a
 * view that has only just received its scene may not have drawn it yet. */
async function selectThePlant(page: Page): Promise<void> {
  const selected = page.getByTestId("selected-entity");
  await expect(async () => {
    await clickAt(page, STEM, ALONG_THE_ROW);
    await expect(selected).toHaveText(new RegExp(`^${PLANT}_`), { timeout: 500 });
  }).toPass();
}

test("crop: the reference greenhouse's plants live each day in the house's air and their own light", async ({
  page,
}) => {
  test.setTimeout(300_000);
  const status = page.getByTestId("scene-status");
  const run = page.getByRole("group", { name: "Climate run" });

  await test.step("before its first day ends, its transplants have lived no day", async () => {
    await page.goto(`/?scenario=reference_greenhouse&field=climate&t=${NOON_S}&camera=${CAMERA}`);
    await expect(status).toContainText("reference_greenhouse, day 0, 3108 entities", ARRIVES);
    await expect(page.getByTestId("field-status")).toContainText("cells", ARRIVES);
    await selectThePlant(page);
    await expect(page.getByTestId("plant-days")).toContainText("No day lived yet", ARRIVES);
    // Its own light at noon, and through its first day, at its crown's top.
    await expect(page.getByTestId("plant-par")).toHaveText("760 µmol/m²/s", ARRIVES);
    await expect(page.getByTestId("plant-daily-light")).toHaveText("18.0 mol/m²/d");
  });

  await test.step("a day on, it has lived its first, and grown", async () => {
    await run.getByRole("button", { name: "Next day" }).click();
    await expect(page).toHaveURL(new RegExp(`&t=${DAY_S + NOON_S}(&|$)`));
    await expect(status).toContainText("reference_greenhouse, day 1, 3155 entities", ARRIVES);
    // The organ selected is still the same plant's, on its next day.
    await expect(page.getByTestId("selected-entity")).toHaveText(new RegExp(`^${PLANT}_`));
    await expect(page.getByTestId("plant-days-air")).toHaveText(
      "Air 15.5 °C on day 0, 15.5 to 15.5",
      ARRIVES,
    );
    await expect(page.getByTestId("plant-days-light")).toHaveText(
      "Light 18.0 mol/m²/d on day 0, 18.0 to 18.0",
    );
    await expect(page.getByTestId("plant-days-co2")).toHaveText("CO₂ 420 ppm on day 0, 420 to 420");
    await expect(page.getByTestId("plant-daily-light")).toHaveText("18.3 mol/m²/d", ARRIVES);
  });

  await test.step("two days on, its days are charted one by one", async () => {
    await run.getByRole("button", { name: "Next day" }).click();
    await expect(status).toContainText("reference_greenhouse, day 2, 3264 entities", ARRIVES);
    await expect(page.getByTestId("plant-days-light")).toHaveText(
      "Light 18.3 mol/m²/d on day 1, 18.0 to 18.3",
      ARRIVES,
    );
    await expect(page.getByTestId("plant-days-air")).toHaveText(
      "Air 17.1 °C on day 1, 15.5 to 17.1",
    );
    await expect(page.getByRole("figure", { name: "Plant days" }).getByRole("img")).toHaveCount(3);
    await expect(page.locator("details.plant-structure summary")).toHaveText(
      `Plant structure: ${PLANT}`,
    );
  });

  await test.step("without its own schedule, its heater on throughout, the house is warmer", async () => {
    await page.goto(
      `/?scenario=reference_greenhouse&field=climate&t=${2 * DAY_S + NOON_S}&daily=none&set=heater:1&camera=${CAMERA}`,
    );
    await expect(status).toContainText("day 2", ARRIVES);
    await selectThePlant(page);
    await expect(page.getByTestId("plant-days-air")).toHaveText(
      "Air 22.2 °C on day 1, 22.2 to 22.2",
      ARRIVES,
    );
  });
});
