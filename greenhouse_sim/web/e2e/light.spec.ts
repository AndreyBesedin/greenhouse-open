import { expect, test } from "@playwright/test";

// The middle of the climate box's floor, a quarter of a metre up.
const ON_THE_FLOOR = "6:3.2:0.25";

test("light: under a clear sky the floor takes the sun's PAR", async ({ page }) => {
  // 12:45 on 1 January, about solar noon, the sun 15° up: a clear sky's
  // 229.5 W/m² on a level surface, its PAR 2.15 times that.
  await page.goto(
    `/?scenario=climate_box&field=climate&weather=cold_spring_day&t=45900&fieldView=slice&slice=par:z:0.25&probes=${ON_THE_FLOOR}`,
  );
  await expect(page.getByTestId("climate-time")).toHaveText("12 h 45 min");
  // The field at the moment takes a while to work out.
  await expect(page.getByTestId("field-status")).toContainText("cells", { timeout: 60_000 });

  await expect(page.getByTestId("field-legend-quantity")).toHaveText("PAR (µmol/m²/s)");
  await expect(page.getByTestId("probe-1-reading")).toContainText(
    "PAR 492.93 µmol/m²/s, irradiance 229.50 W/m²",
  );
  const weather = page.getByRole("region", { name: "Weather" });
  await weather.getByTestId("weather-summary").click();
  await expect(weather.getByTestId("weather-light")).toHaveText("229 W/m², PAR 493 µmol/m²/s");
});

test("light: at night the floor is dark", async ({ page }) => {
  await page.goto(
    `/?scenario=climate_box&field=climate&weather=cold_spring_day&t=600&probes=${ON_THE_FLOOR}`,
  );
  await expect(page.getByTestId("climate-time")).toHaveText("10 min");
  await expect(page.getByTestId("field-status")).toContainText("cells", { timeout: 20_000 });

  await expect(page.getByTestId("probe-1-reading")).toContainText(
    "PAR 0.00 µmol/m²/s, irradiance 0.00 W/m²",
  );
  const weather = page.getByRole("region", { name: "Weather" });
  await weather.getByTestId("weather-summary").click();
  await expect(weather.getByTestId("weather-light")).toHaveText("dark");
});
