import { expect, test } from "@playwright/test";

// The climate box's heater on at 18 h on its first day, 20 h shown.
const EVENING_S = 64_800;
const SHOWN_S = 72_000;
const DAY_S = 86_400;
// A moment on a later day takes the simulator a grid run of its own; the
// heater's level is the scene's, asked for beside it.
const ARRIVES = { timeout: 40_000 };

test("daily schedule: a command repeated every day runs every day, until overridden or taken out", async ({
  page,
}) => {
  test.setTimeout(180_000);
  await page.goto(
    `/?scenario=climate_box&field=climate&t=${SHOWN_S}&schedule=${EVENING_S}:heater:1`,
  );
  const run = page.getByRole("group", { name: "Climate run" });
  const moment = page.getByTestId("climate-time");
  const schedule = page.getByRole("region", { name: "Schedule" });
  const heater = page.getByTestId("equipment-heater");
  const nextDay = run.getByRole("button", { name: "Next day" });

  await test.step("repeated, the evening's command becomes every evening's", async () => {
    await expect(moment).toHaveText("20 h 00 min", ARRIVES);
    await expect(heater).toHaveText("100%, 10 kW", ARRIVES);
    await schedule
      .getByRole("button", { name: "Repeat heater 100% at 18 h 00 min every day" })
      .click();
    await expect(page).toHaveURL(new RegExp(`&daily=${EVENING_S}:heater:1(&|$)`));
    await expect(page).not.toHaveURL(/&schedule=/);
    await expect(schedule.getByTestId("daily-command")).toHaveText(/every day 18 h 00 min/);
    await expect(heater).toHaveText("100%, 10 kW", ARRIVES);
  });

  await test.step("the next evening, the heater runs again", async () => {
    await nextDay.click();
    await expect(moment).toHaveText("day 1, 20 h 00 min", ARRIVES);
    await expect(heater).toHaveText("100%, 10 kW", ARRIVES);
  });

  await test.step("switched off that evening, it is off then, and on the next", async () => {
    await page
      .getByRole("group", { name: "Equipment" })
      .getByRole("checkbox", { name: "heater" })
      .uncheck();
    await expect(page).toHaveURL(new RegExp(`&schedule=${DAY_S + SHOWN_S}:heater:0(&|$)`));
    await expect(heater).toHaveText("off", ARRIVES);
    await nextDay.click();
    await expect(moment).toHaveText("day 2, 20 h 00 min", ARRIVES);
    await expect(heater).toHaveText("100%, 10 kW", ARRIVES);
  });

  await test.step("taken out, it runs no more", async () => {
    await schedule
      .getByRole("button", { name: "Remove heater 100% every day at 18 h 00 min" })
      .click();
    await expect(page).not.toHaveURL(/&daily=/);
    await expect(heater).toHaveText("off", ARRIVES);
  });
});
