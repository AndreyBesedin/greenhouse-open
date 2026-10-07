import { expect as baseExpect, test } from "@playwright/test";

import { PLANT_LAB_LAST_DAY } from "../src/plants/lab.ts";

// The P03 final QA, `tomato-season`, as a walk through the plant lab: watch
// the row grow, name its plants, hold it to the structure's rules, and
// check that seeds repeat and differ. Growing the row on its later days, and
// drawing it in software, takes a while.
const SEASON_EXPECT_TIMEOUT_MS = 30_000;
const expect = baseExpect.configure({ timeout: SEASON_EXPECT_TIMEOUT_MS });
test.beforeEach(() => {
  test.slow();
});
// The lab's row.
const ROW_PLANTS = 20;

test("the season plays day after day, and stops when paused", async ({ page }) => {
  await page.goto("/?plants=lab");
  await expect(page.getByTestId("plant-day")).toHaveText("day 0");
  await page.getByRole("combobox", { name: "Growth speed" }).selectOption("5");

  await page.getByRole("button", { name: "Play the run" }).click();

  await expect(page.getByTestId("plant-day")).toHaveText(/^day ([3-9]|\d\d)$/);
  await page.getByRole("button", { name: "Pause the run" }).click();
  const paused = await page.getByTestId("plant-day").textContent();
  await page.waitForTimeout(1500);
  await expect(page.getByTestId("plant-day")).toHaveText(paused ?? "");
  await expect(page).toHaveURL(new RegExp(`day=${paused?.replace("day ", "")}$`));
});

test("every plant is named, and keeps the structure's rules all season", async ({ page }) => {
  await page.goto("/?plants=lab&day=45");
  await expect(page.getByTestId("rule-checks")).toHaveText(
    `On day 45, all ${ROW_PLANTS} plants keep the structure's rules.`,
  );

  await page.getByRole("checkbox", { name: "Plant names" }).check();

  const names = page.getByTestId("debug-label");
  await expect(names).toHaveCount(ROW_PLANTS);
  await expect(names.first()).toHaveText("p01");

  await page.getByRole("slider").fill(String(PLANT_LAB_LAST_DAY));
  await expect(page.getByTestId("rule-checks")).toHaveText(
    `On day ${PLANT_LAB_LAST_DAY}, all ${ROW_PLANTS} plants keep the structure's rules.`,
  );
});

test("the same seed repeats the season exactly, and another varies it", async ({ page }) => {
  const scene = async (seed: number) =>
    (await page.request.get(`/api/plants/scene?day=60&seed=${seed}`)).json();
  const first = await scene(3);
  const again = await scene(3);
  const another = await scene(4);

  expect(again).toEqual(first);
  expect(another.entities).not.toEqual(first.entities);
});
