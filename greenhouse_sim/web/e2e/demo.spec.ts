import { expect, type Page, test } from "@playwright/test";

import { QA_REFERENCE_PATH } from "../src/qa/referencePage.ts";

// P09.9: the final QA of P09 (docs/demo.md), walked through as one scripted
// demo of the reference greenhouse. As a browser test it runs on its own,
// after the other day-by-day specs; `npm run demo:record` records it as a
// video (playwright.demo.config.ts), lingering on each step for
// DEMO_PAUSE_MS and captioning it.

const PAUSE_MS = Number(process.env.DEMO_PAUSE_MS ?? 0);
const ARRIVES = { timeout: 180_000 };
const HOUR_S = 3_600;
const STARTED = Date.now();

/** Shows a step's caption over the page, for the video, and lingers on it. */
async function say(page: Page, caption: string): Promise<void> {
  console.log(`STEP ${((Date.now() - STARTED) / 1000).toFixed(0)} s: ${caption}`);
  await page.evaluate((text) => {
    const shown =
      document.getElementById("demo-caption") ??
      document.body.appendChild(
        Object.assign(document.createElement("div"), { id: "demo-caption" }),
      );
    shown.textContent = text;
    shown.setAttribute(
      "style",
      "position:fixed;left:50%;bottom:16px;transform:translateX(-50%);z-index:1000;" +
        "padding:8px 14px;border-radius:6px;background:rgb(0 0 0 / 75%);color:#fff;" +
        "font:16px system-ui;pointer-events:none",
    );
  }, caption);
  await linger(page);
}

async function linger(page: Page): Promise<void> {
  if (PAUSE_MS > 0) {
    await page.waitForTimeout(PAUSE_MS);
  }
}

test("the reference greenhouse's demo walks through P09's final QA", async ({ page }) => {
  test.setTimeout(900_000);
  const moment = page.getByTestId("climate-time");
  const run = page.getByRole("group", { name: "Climate run" });

  // 1. The reference scenario, seed 42, opened on its first day with red fruit.
  await page.goto("/");
  await say(page, "1. The reference greenhouse, seed 42, from the scenario list");
  await page.getByRole("button", { name: "Show reference_greenhouse" }).click();
  await expect(moment).toHaveText("day 86, 12 h 00 min", ARRIVES);
  await expect(page.getByTestId("scene-status")).toContainText("day 86,", ARRIVES);
  await expect(page.getByTestId("field-status")).toContainText("cells", ARRIVES);
  await say(page, "1. Opened on day 86, its first day with red fruit");

  // 2. The house's dimensions and the crop's layout.
  const dimensions = page.getByRole("checkbox", { name: "Dimensions and axis labels" });
  await dimensions.check();
  await expect(page.getByTestId("debug-label").first()).toBeVisible();
  await say(page, "2. The house measured: 12 × 9.6 m, four rows of eight plants");
  await dimensions.uncheck();

  // 3. Morning to noon: the sun, its shadows and its light.
  const timeOfDay = run.getByRole("slider", { name: "Time of day" });
  await timeOfDay.fill(String(6 * HOUR_S));
  await expect(moment).toHaveText("day 86, 6 h 00 min", ARRIVES);
  await say(page, "3. Dawn: the sun 11° up in the east-north-east, its shadows long");
  await timeOfDay.fill(String(12 * HOUR_S + 40 * 60));
  await expect(moment).toHaveText("day 86, 12 h 40 min", ARRIVES);
  await expect(page.getByTestId("field-status")).toContainText("cells", ARRIVES);
  await say(page, "3. The sun's noon, 12:40: 59° up in the south");

  // 4. The air: its vectors, then a slice of its temperature.
  await say(page, "4. The air as arrows: the fans' jets down the house");
  await page.getByRole("radio", { name: "slice" }).check();
  await page.getByLabel("Slice of").selectOption("temperature");
  await expect(page.getByTestId("field-legend-quantity")).toContainText("temperature");
  await say(page, "4. A slice of the air's temperature");

  // 5. The equipment: the dehumidifier on, from this moment.
  await page
    .getByRole("group", { name: "Equipment" })
    .getByRole("checkbox", { name: "dehumidifier" })
    .check();
  await expect(page).toHaveURL(/dehumidifier/);
  await expect(page.getByTestId("field-status")).toContainText("cells", ARRIVES);
  await say(page, "5. The dehumidifier on: the air dries around it");

  // 6. The roof vents, open by the schedule: shut before 9:00, half open
  // from 9:00 and fully from 11:00; then one shut by hand, a command at the
  // moment, the run carried on rather than worked out again. The wind is
  // turned last.
  const vent = page.getByTestId("opening-roof_vent_1");
  await timeOfDay.fill(String(8 * HOUR_S));
  await expect(moment).toHaveText("day 86, 8 h 00 min", ARRIVES);
  await expect(vent).toHaveText(/^0%, /, ARRIVES);
  await say(page, "6. At 8:00 the roof vents are shut");
  await timeOfDay.fill(String(11 * HOUR_S));
  await expect(moment).toHaveText("day 86, 11 h 00 min", ARRIVES);
  await expect(vent).toHaveText(/^100%, /, ARRIVES);
  await say(page, "6. From 11:00 the schedule has them fully open");
  await page.getByRole("group", { name: "Openings" }).getByRole("slider").first().fill("0");
  await expect(page).toHaveURL(/7470000:roof_vent_1:0/);
  await expect(vent).toHaveText(/^0%, /, ARRIVES);
  await expect(page.getByTestId("field-status")).toContainText("cells", ARRIVES);
  await say(page, "6. One shut by hand at 11:00: a command at that moment");

  // 7. A sensor's readings against QA mode's truth, early in the day: its
  // log is read from the day's start, which at noon would take minutes. Not
  // in the day's first hour, though: a field then starts its grid run an
  // hour before the day began, which the kept opening day does not hold,
  // and the season is worked out afresh. QA mode's developer panel lists
  // the sensors, and selects one: in a crop this dense it is easier found
  // there than in the view.
  await page.getByRole("checkbox", { name: "QA mode" }).check();
  const developer = page.getByRole("region", { name: "QA mode" });
  // The panel settled first, then the moment moved: a slider filled while
  // the panels around it are drawn anew can lose its change.
  await expect(page.getByTestId("developer-clock")).toContainText("day 86, 11 h 00 min", ARRIVES);
  await expect(async () => {
    await timeOfDay.fill(String(HOUR_S + 20 * 60));
    await expect(moment).toHaveText("day 86, 1 h 20 min", { timeout: 5_000 });
  }).toPass(ARRIVES);
  await expect(page.getByTestId("developer-clock")).toContainText("day 86, 1 h 20 min", ARRIVES);
  await say(page, "7. QA mode's developer panel: what every process holds now");
  await developer.getByRole("button", { name: /^temperature_back: / }).click();
  const selected = page.getByTestId("selected-entity");
  await expect(selected).toHaveText("reference_greenhouse_temperature_back");
  const sensor = page.getByRole("region", { name: "Sensor" });
  await expect(sensor.getByTestId("sensor-truth")).toContainText("°C", ARRIVES);
  await say(page, "7. The back sensor's readings against what was truly there");

  // 8. The fixed camera: its picture, its depth and its instances.
  await developer.getByRole("button", { name: /^path_camera: / }).click();
  await expect(selected).toHaveText("reference_greenhouse_path_camera");
  const camera = page.getByRole("region", { name: "Camera" });
  await expect(camera.getByTestId("camera-view")).toBeVisible();
  await say(page, "8. The path camera's picture");
  await camera.getByRole("tab", { name: "Depth" }).click();
  await expect(camera.getByTestId("camera-depth-range")).toBeVisible(ARRIVES);
  await say(page, "8. Its depth");
  // Its instances: the list of what is in view runs to thousands of organs,
  // which the camera's own browser tests read.
  const instances = camera.getByRole("tab", { name: "Instance" });
  await instances.click();
  await expect(instances).toHaveAttribute("aria-selected", "true");
  await say(page, "8. And what each pixel shows");
  // Put away: a selected camera draws its passes again with every scene.
  await page
    .getByRole("region", { name: "Inspector" })
    .getByRole("button", { name: "Clear selection" })
    .click();
  await expect(selected).toHaveCount(0);

  // 9. The crop, a day on: no two plants alike, its fruit ripening.
  await run.getByRole("button", { name: "Next day" }).click();
  await expect(moment).toHaveText(/^day 87, /, ARRIVES);
  await expect(page.getByTestId("scene-status")).toContainText("day 87,", ARRIVES);
  await say(page, "9. A day on: each plant drawn from seed 42, its fruit ripening");

  // 10. A harvest, by hand in the plant lab, in the plant's history.
  await page.goto("/?plants=lab&day=85");
  await expect(page.getByTestId("scene-status")).toContainText("day 85", ARRIVES);
  await say(page, "10. The plant lab: a red fruit");
  await page.getByRole("button", { name: "p01_t01_fr01", exact: true }).click();
  await page.getByRole("button", { name: "Harvest this fruit" }).click();
  await expect(page.getByTestId("plant-event")).toHaveText([
    /^at \d+ °Cd: harvested p01_t01_fr01, \d+ g$/,
  ]);
  await say(page, "10. Harvested, and kept in the plant's history");

  // 11. A checkpoint, a branch, and two schedules compared.
  await page.goBack();
  await expect(moment).toHaveText(/^day 87, /, ARRIVES);
  const checkpoints = page.locator("details", { hasText: "Checkpoints" });
  await checkpoints.locator("summary").click();
  await checkpoints.getByRole("button", { name: "Save day 87's start" }).click();
  // Listed beside the kept opening day, day 86, the earliest first.
  const compare = checkpoints.getByRole("button", { name: /^Compare with day 87, / });
  await expect(compare).toBeVisible(ARRIVES);
  await say(page, "11. Day 87's start saved");
  // Its thermostat runs the heater through the night: a branch turns it off.
  await page
    .getByRole("group", { name: "Equipment" })
    .getByRole("checkbox", { name: "heater" })
    .uncheck();
  await compare.click();
  const branches = page.getByRole("region", { name: "Branches" });
  await expect(branches.getByTestId("branches-house")).toBeVisible(ARRIVES);
  await say(page, "11. A branch with the heater off, against the checkpoint's run");

  // 6, last: the wind turned. Under another wind the run is another run,
  // which no kept day of the season's fits: its air is worked out afresh
  // from its start, minutes in all, so the walk-through turns it last and
  // shows the weather turning, not the air it makes.
  const weather = page.getByRole("region", { name: "Weather" });
  await weather.locator("summary").click();
  await weather.getByRole("slider", { name: "Wind direction" }).fill("90");
  await expect(page).toHaveURL(/&wind=90/);
  await expect(page.getByTestId("wind-compass")).toBeVisible();
  await say(page, "6. The wind turned to blow from the east: another run, worked out afresh");

  // 12. Seed 42 again: the golden views and their state probes. The viewer
  // is left for a blank page first: the turned wind's requests, each waiting
  // minutes on its run, hold the browser's six connections to the viewer's
  // host, and a page asked of it waits until one ends (on a slow machine,
  // past the test's timeout). A blank page needs none, and leaving the
  // viewer ends them.
  await page.goto("about:blank");
  await page.goto(`${QA_REFERENCE_PATH}?view=noon`);
  await expect(page.getByTestId("qa-probes")).toContainText("house air 28.16 °C", ARRIVES);
  await say(page, "12. The golden views, as CI compares them, with their state probes");
});
