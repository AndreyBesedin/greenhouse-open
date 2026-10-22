import { expect, type Page, test } from "@playwright/test";
import type { CameraPose } from "../src/camera.ts";
import { chooser } from "./chooser";
import { unfold } from "./folds";
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
    await expect(status).toContainText("reference_greenhouse, day 0, 3106 entities", ARRIVES);
    await expect(page.getByTestId("field-status")).toContainText("cells", ARRIVES);
    await selectThePlant(page);
    await expect(page.getByTestId("plant-days")).toContainText("No day lived yet", ARRIVES);
    // Its own light at noon, and through its first day, a dull one, at its
    // crown's top.
    await expect(page.getByTestId("plant-par")).toHaveText("370 µmol/m²/s", ARRIVES);
    await expect(page.getByTestId("plant-daily-light")).toHaveText("9.0 mol/m²/d");
  });

  await test.step("a day on, it has lived its first, and grown", async () => {
    await run.getByRole("button", { name: "Next day" }).click();
    await expect(page).toHaveURL(new RegExp(`&t=${DAY_S + NOON_S}(&|$)`));
    await expect(status).toContainText("reference_greenhouse, day 1, 3159 entities", ARRIVES);
    // The organ selected is still the same plant's, on its next day.
    await expect(page.getByTestId("selected-entity")).toHaveText(new RegExp(`^${PLANT}_`));
    await expect(page.getByTestId("plant-days-air")).toHaveText(
      "Air 17.0 °C on day 0, 17.0 to 17.0",
      ARRIVES,
    );
    await expect(page.getByTestId("plant-days-light")).toHaveText(
      "Light 9.0 mol/m²/d on day 0, 9.0 to 9.0",
    );
    await expect(page.getByTestId("plant-days-co2")).toHaveText("CO₂ 420 ppm on day 0, 420 to 420");
    await expect(page.getByTestId("plant-daily-light")).toHaveText("19.6 mol/m²/d", ARRIVES);
  });

  await test.step("two days on, its days are charted one by one", async () => {
    await run.getByRole("button", { name: "Next day" }).click();
    await expect(status).toContainText("reference_greenhouse, day 2, 3279 entities", ARRIVES);
    await expect(page.getByTestId("plant-days-light")).toHaveText(
      "Light 19.6 mol/m²/d on day 1, 9.0 to 19.6",
      ARRIVES,
    );
    await expect(page.getByTestId("plant-days-air")).toHaveText(
      "Air 17.0 °C on day 1, 17.0 to 17.0",
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
      "Air 27.4 °C on day 1, 26.9 to 27.4",
      ARRIVES,
    );
  });
});

// The reference run's kept opening day (P09.5): shown from the list, it
// opens on its first day with red fruit, day 86, which the API keeps as it
// starts, so that the day is not worked out from the run's start.
test("crop: shown from the list, the reference greenhouse opens on its first day with red fruit", async ({
  page,
}) => {
  test.setTimeout(300_000);
  await page.goto("/");
  await (await chooser(page)).getByRole("button", { name: "Open reference_greenhouse" }).click();
  await expect(page).toHaveURL(/[?&]field=climate(&|$)/);
  await expect(page).toHaveURL(new RegExp(`&t=${86.5 * DAY_S}(&|$)`));
  await expect(page.getByTestId("climate-time")).toHaveText("day 86, 12 h 00 min", ARRIVES);
  await expect(page.getByTestId("scene-status")).toContainText(
    "reference_greenhouse, day 86,",
    ARRIVES,
  );
  // Its air at noon, the vents open, drawn cell by cell: waited for, so that
  // the simulator is not still working it out when the next spec begins.
  await expect(page.getByTestId("field-status")).toContainText("cells", ARRIVES);
  // Its house's air beside the same run's with everything off, kept too.
  await unfold(page, "House air");
  await expect(
    page.getByRole("figure", { name: "House air" }).getByTestId("house-air-°C"),
  ).toHaveText(/^Air [\d.]+ °C, all off [\d.]+ °C$/, ARRIVES);
});

test("crop: stepped on from its opening day, a day given up on the way, the crop is drawn throughout (#197)", async ({
  page,
}) => {
  test.setTimeout(300_000);
  // From its opening day (86), where the viewer opens it, as the QA stepped
  // on from it; the days before it are worked out from the run's start, so
  // the simulator's tests cover the crop on days 83 and 85 (#197). Some
  // 13,000 entities are drawn on these days; without a day's crop, the
  // scene draws its transplants in its place, some 3,000.
  const WHOLE = 10_000;
  const status = page.getByTestId("scene-status");
  const moment = page.getByTestId("climate-time");
  const pending = page.getByTestId("climate-pending");
  const next = page.getByRole("group", { name: "Climate run" }).getByRole("button", {
    name: "Next day",
  });
  /** The entities drawn, as the scene's status counts them. */
  const drawn = async (): Promise<number> =>
    Number(/([\d,]+) entities/.exec((await status.textContent()) ?? "")?.[1]?.replaceAll(",", ""));
  /** What is drawn while a step is on its way, sampled until it arrives. */
  async function whileOnItsWay(day: number): Promise<number[]> {
    const seen: number[] = [];
    while ((await moment.textContent()) !== `day ${day}, 10 min` || (await pending.isVisible())) {
      seen.push(await drawn());
      await page.waitForTimeout(250);
    }
    return seen;
  }

  await page.goto(`/?scenario=reference_greenhouse&field=climate&t=${86 * DAY_S + 600}`);
  await expect(moment).toHaveText("day 86, 10 min", ARRIVES);
  await expect(pending).toBeHidden(ARRIVES);
  await expect(status).toContainText("reference_greenhouse, day 86,");
  const counts = [await drawn()];

  // Day 87 asked for and given up for 88 before it arrives: two requests
  // overlapping, the first superseded.
  await next.click();
  await next.click();
  const steps = [...(await whileOnItsWay(88))];
  counts.push(await drawn());
  for (const day of [89, 90]) {
    await next.click();
    steps.push(...(await whileOnItsWay(day)));
    await expect(status).toContainText(`reference_greenhouse, day ${day},`);
    counts.push(await drawn());
  }

  expect(Math.min(...counts, ...steps)).toBeGreaterThan(WHOLE);
});
