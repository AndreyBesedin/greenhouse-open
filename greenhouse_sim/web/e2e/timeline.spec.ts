import { expect, test } from "@playwright/test";

// The climate box's heater switched on ten minutes into its run (P09.2): its
// twelve sensors and its camera sample every minute, and its air is worked
// on a minute at a time.
const HEATED_AT_TEN_MINUTES = "/?scenario=climate_box&field=climate&t=600&schedule=600:heater:1";

test("timeline: each process's events at its own cadence, in their turns at a moment", async ({
  page,
}) => {
  await page.goto(HEATED_AT_TEN_MINUTES);
  await expect(page.getByTestId("climate-time")).toHaveText("10 min", { timeout: 20_000 });
  const timeline = page.locator("details.timeline");
  await timeline.getByText("Timeline").click();
  const lane = (process: string) => page.getByTestId(`timeline-${process}`);

  await test.step("over the hour the moment lies in", async () => {
    await expect(lane("commands")).toHaveText("commands, 1");
    await expect(lane("air")).toHaveText("air, 60");
    await expect(lane("plants")).toHaveText("plants, 0");
    // Each a sample a minute, and one at the run's start.
    await expect(lane("sensors")).toHaveText("sensors, 732");
    await expect(lane("cameras")).toHaveText("cameras, 61");
  });

  await test.step("at the moment, the command first, then the air, sensors and camera", async () => {
    await expect(page.getByTestId("timeline-turn")).toHaveText([
      "commands: heater set to 1",
      "air: house step",
      "sensors: 12 × sample",
      "cameras: front_camera frame",
    ]);
  });

  await test.step("over the day, each plant grows its day at its end", async () => {
    await page.getByRole("combobox", { name: "Timeline zoom" }).selectOption({ label: "a day" });
    await expect(lane("plants")).toHaveText("plants, 32");
    await expect(lane("air")).toHaveText("air, 1440");
  });

  await test.step("over a minute, one turn of each", async () => {
    await page.getByRole("combobox", { name: "Timeline zoom" }).selectOption({ label: "a minute" });
    await expect(lane("sensors")).toHaveText("sensors, 12");
    await expect(lane("air")).toHaveText("air, 1");
  });
});
