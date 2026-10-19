import { expect, test } from "@playwright/test";

// The reference run's own schedule (P09.4): its manifest heats, vents and
// stirs the house by the clock every day, the heater full from 17 h and set
// back to 80% at 23 h, unless the address gives daily commands of its own.
const DAY_S = 86_400;
const SECOND_EVENING_S = DAY_S + 22 * 3600;
// A later day's moment takes the simulator the house's air through the days
// before it.
const ARRIVES = { timeout: 90_000 };

test("reference schedule: the run heats by its own clock, set back at night, unless the address changes it", async ({
  page,
}) => {
  test.setTimeout(300_000);
  const run = page.getByRole("group", { name: "Climate run" });
  const moment = page.getByTestId("climate-time");
  const heater = page.getByTestId("equipment-heater");
  const air = page.getByRole("figure", { name: "House air" }).getByTestId("house-air-°C");
  const schedule = page.getByRole("region", { name: "Schedule" });
  const daily = schedule.getByTestId("daily-command");
  const summary = schedule.getByTestId("schedule-summary");

  await test.step("in its second evening, the heater runs in full by its own schedule", async () => {
    await page.goto(`/?scenario=reference_greenhouse&field=climate&t=${SECOND_EVENING_S}`);
    await expect(moment).toHaveText("day 1, 22 h 00 min", ARRIVES);
    await expect(daily).toHaveCount(21);
    // Folded, its 21 commands are a line, and the next of them.
    await expect(summary).toHaveText(
      "Schedule: 21 commands. Next at day 1, 23 h 00 min: heater 80%.",
    );
    await expect(daily.first()).toBeHidden();
    await expect(heater).toHaveText("100%, 15 kW", ARRIVES);
    await expect(air).toHaveText("Air 18.9 °C, all off 10.7 °C", ARRIVES);
    // The address keeps no copy of the scenario's own schedule.
    expect(page.url()).not.toContain("daily=");
  });

  await test.step("in the small hours, set back, the house cools, still well above all off", async () => {
    await run.getByRole("button", { name: "Next day" }).click();
    await run.getByRole("slider", { name: "Time of day" }).fill("10800");
    await expect(moment).toHaveText("day 2, 3 h 00 min", ARRIVES);
    await expect(heater).toHaveText("80%, 12 kW", ARRIVES);
    await expect(air).toHaveText("Air 13.1 °C, all off 5.2 °C", ARRIVES);
  });

  await test.step("its setback taken out, the address keeps the rest, and the heater runs on", async () => {
    // Opened from the keyboard, as its summary is a control.
    await schedule.locator("summary").press("Enter");
    await expect(daily.first()).toBeVisible();
    await schedule
      .getByRole("button", { name: "Remove heater 80% every day at 23 h 00 min" })
      .click();
    await expect(page).toHaveURL(/&daily=/);
    await expect(daily).toHaveCount(20);
    await expect(summary).toHaveText(
      "Schedule: 20 commands. Next at day 2, 5 h 00 min: heater 100%.",
    );
    await expect(heater).toHaveText("100%, 15 kW", ARRIVES);
  });
});

// The final QA's sixth step: open a door, and turn the outside wind.
test("reference wind: an open door's flow turns with the wind, overridden for QA", async ({
  page,
}) => {
  test.setTimeout(240_000);
  const weather = page.getByRole("region", { name: "Weather" });
  const labels = page.getByTestId("debug-label");

  await page.goto("/?scenario=reference_greenhouse&field=climate&t=43200&open=door:1");
  await expect(page.getByTestId("climate-time")).toHaveText("12 h 00 min", ARRIVES);
  // Opened once it has read the weather.
  await expect(weather.getByTestId("weather-summary")).toContainText("Outside at", ARRIVES);
  await weather.getByTestId("weather-summary").click();
  // From the west at noon, its own, the wind blows in through the front door.
  await expect(weather.getByTestId("weather-wind")).toContainText("(270°)", ARRIVES);
  await expect(weather.getByTestId("weather-wind-override")).toHaveText("its own");
  await expect(labels.filter({ hasText: /^11\.\d\d m³\/s in$/ })).toHaveCount(1, ARRIVES);

  // From the north, the house draws out through it.
  await weather.getByRole("slider", { name: "Wind direction" }).fill("0");
  await expect(page).toHaveURL(/&wind=0(&|$)/);
  await expect(weather.getByTestId("weather-wind-override")).toHaveText("0°, for QA");
  await expect(weather.getByTestId("weather-wind")).toContainText("(0°)", ARRIVES);
  await expect(labels.filter({ hasText: /^2\.\d\d m³\/s out$/ })).toHaveCount(1, ARRIVES);

  await weather.getByRole("button", { name: "Its own wind" }).click();
  await expect(page).not.toHaveURL(/&wind=/);
});
