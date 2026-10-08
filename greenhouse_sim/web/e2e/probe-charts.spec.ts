import { expect, test } from "@playwright/test";

// Beside the climate box's heater, and in the middle of the house, both
// 0.75 m up.
const BY_THE_HEATER = "10.5:1:0.75,6:3.2:0.75";

test("probe charts: a heated run diverges from the same run all off, where the heater acts", async ({
  page,
}) => {
  await page.goto(
    `/?scenario=climate_box&set=heater:1&field=climate&t=600&probes=${BY_THE_HEATER}`,
  );
  const charts = page.getByRole("region", { name: "Probe charts" });
  const corner = page.getByTestId("chart-P1-temperature_c");
  const middle = page.getByTestId("chart-P2-temperature_c");

  await test.step("ten minutes in, the heated corner is far warmer than all off", async () => {
    await expect(corner).toHaveText("temperature 31.88 °C, all off 9.01 °C");
    await expect(middle).toHaveText("temperature 14.96 °C, all off 9.13 °C");
    await expect(page.getByTestId("chart-P1-humidity_pct")).toHaveText(
      "humidity 31.58 %, all off 100.00 %",
    );
    // Two lines a chart, three charts a probe.
    await expect(charts.locator("polyline")).toHaveCount(12);
  });

  await test.step("the charts read what the probes read", async () => {
    await expect(page.getByTestId("probe-1-reading")).toHaveText(
      /temperature 31\.88 °C, humidity 31\.58 %$/,
    );
    await expect(page.getByTestId("probe-2-reading")).toHaveText(
      /temperature 14\.96 °C, humidity 84\.80 %$/,
    );
  });

  await test.step("later in the run, the charts follow", async () => {
    await page.getByRole("slider", { name: "Time into the run" }).fill("1200");
    await expect(corner).toHaveText("temperature 31.83 °C, all off 8.13 °C");
    await expect(middle).toHaveText("temperature 14.89 °C, all off 8.14 °C");
  });
});
