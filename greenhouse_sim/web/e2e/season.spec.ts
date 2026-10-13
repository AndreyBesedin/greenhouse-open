import { expect, test } from "@playwright/test";

// The climate box's runs last its 14 days (P09.2): its heater on ten minutes
// into the first, and off an hour into the second.
const SCHEDULE = "600:heater:1,90000:heater:0";
const DAY_S = 86_400;
// A moment on a later day takes the simulator a grid run of its own; the
// heater's level is the scene's, asked for beside it.
const ARRIVES = { timeout: 40_000 };

test("season: the time controls span the run's days, each chart its moment's day", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await page.goto(`/?scenario=climate_box&field=climate&t=600&schedule=${SCHEDULE}`);
  const run = page.getByRole("group", { name: "Climate run" });
  const day = run.getByRole("slider", { name: "Day of the run" });
  const moment = page.getByTestId("climate-time");
  const heater = page.getByTestId("equipment-heater");
  const markers = page.getByRole("region", { name: "Schedule" }).getByTestId("schedule-marker");

  await test.step("on the first day, there is no day before it", async () => {
    await expect(moment).toHaveText("10 min", ARRIVES);
    await expect(day).toHaveValue("0");
    await expect(run.getByRole("button", { name: "Previous day" })).toBeDisabled();
    await expect(heater).toHaveText("100%, 10 kW", ARRIVES);
    // The bar is the day's: only the first command lies on it.
    await expect(markers).toHaveCount(1);
  });

  await test.step("a day on, the same time of day, and the weather of that day", async () => {
    const weatherDay = page.waitForRequest(/\/weather\/day\?t=172800/);
    await run.getByRole("button", { name: "Next day" }).click();
    await expect(page).toHaveURL(new RegExp(`&t=${DAY_S + 600}(&|$)`));
    await expect(moment).toHaveText("day 1, 10 min", ARRIVES);
    await weatherDay;
    await expect(day).toHaveValue("1");
    // Still on from the first day, until its command an hour in.
    await expect(heater).toHaveText("100%, 10 kW", ARRIVES);
    await expect(markers).toHaveCount(1);
    await expect(page.getByTestId("house-air")).toBeVisible();
    await run.getByRole("slider", { name: "Time of day" }).fill("3600");
    await expect(moment).toHaveText("day 1, 1 h 00 min", ARRIVES);
    await expect(heater).toHaveText("off", ARRIVES);
  });

  await test.step("on its last day, there is none after it", async () => {
    await day.fill("13");
    await expect(moment).toHaveText("day 13, 1 h 00 min", ARRIVES);
    await expect(run.getByRole("button", { name: "Next day" })).toBeDisabled();
    await expect(markers).toHaveCount(0);
  });

  await test.step("played a day a step, it keeps its time of day, and stops at the end", async () => {
    await day.fill("12");
    await expect(moment).toHaveText("day 12, 1 h 00 min", ARRIVES);
    await run.getByRole("combobox", { name: "Pace" }).selectOption({ label: "1 day a step" });
    await run.getByRole("button", { name: "Play" }).click();
    await expect(moment).toHaveText("day 13, 1 h 00 min", ARRIVES);
    await expect(moment).toHaveText("day 13, 24 h 00 min", ARRIVES);
    await expect(run.getByRole("button", { name: "Play" })).toBeVisible();
    await expect(page).toHaveURL(new RegExp(`&t=${14 * DAY_S}(&|$)`));
  });
});
