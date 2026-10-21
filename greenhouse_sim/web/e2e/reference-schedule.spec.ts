import { expect, test } from "@playwright/test";

import { unfold } from "./folds";

// The reference run's own schedule (P09.4) and its thermostat (P10.3): its
// manifest vents and stirs the house by the clock every day, unless the
// address gives daily commands of its own, and its thermostat heats it to
// 16 °C by night and 18 °C by day, as the air needs; a command to the
// heater takes it over.
const DAY_S = 86_400;
const SECOND_EVENING_S = DAY_S + 22 * 3600;
// A later day's moment takes the simulator the house's air through the days
// before it.
const ARRIVES = { timeout: 90_000 };

test("reference schedule: the run vents by its own clock, its thermostat heats it, and a command takes the heater over", async ({
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

  await test.step("in its second evening, the thermostat heats the house to the night's 16 °C", async () => {
    await page.goto(`/?scenario=reference_greenhouse&field=climate&t=${SECOND_EVENING_S}`);
    await expect(moment).toHaveText("day 1, 22 h 00 min", ARRIVES);
    // Its vents and fans by the clock; its heater by no command.
    await expect(daily).toHaveCount(16);
    await expect(summary).toHaveText(
      "Schedule: 16 commands. Next at day 2, 8 h 00 min: fan left 100% and 1 more.",
    );
    await expect(daily.first()).toBeHidden();
    await expect(heater).toHaveText("100%, 30 kW, by its thermostat at 16 °C", ARRIVES);
    await unfold(page, "House air");
    await expect(air).toHaveText("Air 15.7 °C, all off 6.3 °C", ARRIVES);
    // The address keeps no copy of the scenario's own schedule.
    expect(page.url()).not.toContain("daily=");
  });

  await test.step("by the next noon, to the day's 18 °C", async () => {
    await run.getByRole("button", { name: "Next day" }).click();
    await run.getByRole("slider", { name: "Time of day" }).fill("43200");
    await expect(moment).toHaveText("day 2, 12 h 00 min", ARRIVES);
    await expect(heater).toHaveText(/, by its thermostat at 18 °C$/, ARRIVES);
    await expect(air).toHaveText("Air 18.1 °C, all off 13.6 °C", ARRIVES);
  });

  await test.step("switched off by hand, the heater is the command's, not the thermostat's", async () => {
    await unfold(page, "Equipment");
    await page
      .getByRole("group", { name: "Equipment" })
      .getByRole("checkbox", { name: "heater" })
      .uncheck();
    await expect(page).toHaveURL(/&schedule=216000:heater:0/);
    await expect(heater).toHaveText("off", ARRIVES);
  });
});

// The final QA's sixth step: open a door, and turn the outside wind.
test("reference targets: a heating target set from the panel heats the house to it from then on (#274)", async ({
  page,
}) => {
  test.setTimeout(300_000);
  const morning = 7 * 3600 + 30 * 60;
  await page.goto(`/?scenario=reference_greenhouse&field=climate&t=${morning}`);
  const targets = page.locator("details.targets-fold");
  await expect(page.getByTestId("targets-summary")).toHaveText(
    "Heating targets: 18 °C by day, 16 °C by night",
    ARRIVES,
  );

  await test.step("set 24 °C by day at 7 h 30, the address keeps it as a target change", async () => {
    await unfold(page, "Heating targets");
    await targets.getByLabel("By day, °C").fill("24");
    await targets.getByRole("button", { name: "Set from 7 h 30 min" }).click();
    await expect(page).toHaveURL(new RegExp(`targets=${morning}:heating_day:24`));
    await expect(page.getByTestId("targets-summary")).toHaveText(
      "Heating targets: 24 °C by day, 16 °C by night",
      ARRIVES,
    );
  });

  await test.step("an hour later, the thermostat holds the house at 24 °C", async () => {
    await page.getByRole("slider", { name: "Time of day" }).fill(String(morning + 3600));
    await unfold(page, "Equipment");
    await expect(page.getByTestId("equipment-heater")).toHaveText(
      /by its thermostat at 24 °C$/,
      ARRIVES,
    );
    await unfold(page, "House air");
    await expect(page.getByTestId("house-air-°C")).toHaveText(/^Air 2[34]\.\d °C/, ARRIVES);
  });
});

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
  await expect(labels.filter({ hasText: /^0\.\d\d m³\/s out$/ })).toHaveCount(1, ARRIVES);

  await weather.getByRole("button", { name: "Its own wind" }).click();
  await expect(page).not.toHaveURL(/&wind=/);
});
