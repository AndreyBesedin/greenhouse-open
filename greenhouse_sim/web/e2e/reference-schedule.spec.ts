import { expect, test } from "@playwright/test";

// The reference run's own schedule (P09.4): its manifest heats, vents and
// stirs the house by the clock every day, the heater full from 17 h and set
// back to 80% at 23 h, unless the address gives daily commands of its own.
const DAY_S = 86_400;
const SECOND_EVENING_S = DAY_S + 22 * 3600;
// A later day's moment takes the simulator the house's air through the days
// before it.
const ARRIVES = { timeout: 60_000 };

test("reference schedule: the run heats by its own clock, set back at night, unless the address changes it", async ({
  page,
}) => {
  test.setTimeout(180_000);
  const run = page.getByRole("group", { name: "Climate run" });
  const moment = page.getByTestId("climate-time");
  const heater = page.getByTestId("equipment-heater");
  const air = page.getByRole("figure", { name: "House air" }).getByTestId("house-air-°C");
  const daily = page.getByRole("region", { name: "Schedule" }).getByTestId("daily-command");

  await test.step("in its second evening, the heater runs in full by its own schedule", async () => {
    await page.goto(`/?scenario=reference_greenhouse&field=climate&t=${SECOND_EVENING_S}`);
    await expect(moment).toHaveText("day 1, 22 h 00 min", ARRIVES);
    await expect(daily).toHaveCount(21);
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
    await page.getByRole("button", { name: "Remove heater 80% every day at 23 h 00 min" }).click();
    await expect(page).toHaveURL(/&daily=/);
    await expect(daily).toHaveCount(20);
    await expect(heater).toHaveText("100%, 15 kW", ARRIVES);
  });
});
