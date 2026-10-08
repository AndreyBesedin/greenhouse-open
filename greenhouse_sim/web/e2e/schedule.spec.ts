import { expect, test } from "@playwright/test";

// The climate box's fan, heater and dehumidifier switching on on their own,
// a minute apart, with a probe in the fan's core.
const SWITCHING_ON = "60:fan:1,120:heater:1,180:dehumidifier:1";
const IN_THE_FANS_CORE = "3:3.2:2.8";
// A moment of a run, with the fan running, can take CI's simulator a while,
// behind the scene and the charts it is asked for beside it.
const ARRIVES_MS = 20_000;

test("schedule: the equipment switches on its own, and an override holds from its moment", async ({
  page,
}) => {
  await page.goto(
    `/?scenario=climate_box&field=climate&schedule=${SWITCHING_ON}&probes=${IN_THE_FANS_CORE}`,
  );
  const run = page.getByRole("group", { name: "Climate run" });
  const slider = run.getByRole("slider", { name: "Time into the run" });
  const schedule = page.getByRole("region", { name: "Schedule" });
  const commands = schedule.getByTestId("schedule-command");
  const heater = page.getByTestId("equipment-heater");
  const reading = page.getByTestId("probe-1-reading");
  // The moment drawn, once its field has arrived.
  const moment = page.getByTestId("climate-time");

  await test.step("at the start, nothing runs", async () => {
    await expect(commands).toHaveCount(3);
    await expect(page.getByTestId("equipment-fan")).toHaveText("off");
    await expect(heater).toHaveText("off");
    await expect(reading).toHaveText(/^climate: 0\.00 m\/s/);
  });

  await test.step("three minutes in, all three run, as scheduled", async () => {
    await slider.fill("180");
    await expect(moment).toHaveText("3 min", { timeout: ARRIVES_MS });
    await expect(page.getByTestId("equipment-fan")).toHaveText("100%, 1 m³/s");
    await expect(heater).toHaveText("100%, 10 kW");
    await expect(page.getByTestId("equipment-dehumidifier")).toHaveText("100%, 1 kg/h");
    await expect(reading).toHaveText(/^climate: 4\.34 m\/s/);
    await expect(schedule.locator('[data-applied="true"]')).toHaveCount(3);
  });

  await test.step("switched off ten minutes in, the heater is off from then on", async () => {
    await slider.fill("600");
    await expect(moment).toHaveText("10 min", { timeout: ARRIVES_MS });
    await expect(heater).toHaveText("100%, 10 kW");
    await page
      .getByRole("group", { name: "Equipment" })
      .getByRole("checkbox", { name: "heater" })
      .uncheck();
    await expect(page).toHaveURL(
      /&schedule=60:fan:1,120:heater:1,180:dehumidifier:1,600:heater:0(&|$)/,
    );
    await expect(commands).toHaveCount(4);
    await expect(heater).toHaveText("off");
    await slider.fill("540");
    await expect(moment).toHaveText("9 min", { timeout: ARRIVES_MS });
    await expect(heater).toHaveText("100%, 10 kW");
  });

  await test.step("taken out, the override is gone", async () => {
    await schedule.getByRole("button", { name: "Remove heater off at 10 min" }).click();
    await expect(commands).toHaveCount(3);
    await expect(page).toHaveURL(/&schedule=60:fan:1,120:heater:1,180:dehumidifier:1(&|$)/);
    await schedule.getByRole("button", { name: "Go to heater 100% at 2 min" }).click();
    await expect(page).toHaveURL(/&t=120(&|$)/);
    await expect(moment).toHaveText("2 min", { timeout: ARRIVES_MS });
    await expect(heater).toHaveText("100%, 10 kW");
  });
});
