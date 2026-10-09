import { expect, test } from "@playwright/test";

// The middle of the climate box's floor, a quarter of a metre up; and two
// points on the floor's cells' level, in the open south of the first row of
// crop gutters, and north of it, in its shadow at noon in winter.
const ON_THE_FLOOR = "6:3.2:0.25";
const IN_THE_OPEN = "5.75:1.2:0.25";
const IN_THE_SHADE = "5.75:3.2:0.25";

test("light: under a clear sky the floor takes the sun's PAR through the glass, but in shadows", async ({
  page,
}) => {
  // Its climate run is worked out to noon first.
  test.setTimeout(90_000);
  // 12:45 on 1 January, about solar noon, the sun 15° up: the spring day's
  // half-clouded sky gives 213 W/m² on a level surface outside, its PAR 2.15
  // times that, half of it the beam's. Inside, the beam crosses the south
  // wall 15° from square, which passes 84.7% of it; the shade takes the
  // sky's light alone.
  await page.goto(
    `/?scenario=climate_box&field=climate&weather=cold_spring_day&t=45900&fieldView=slice&slice=par:z:0.25&probes=${IN_THE_OPEN},${IN_THE_SHADE}`,
  );
  await expect(page.getByTestId("climate-time")).toHaveText("12 h 45 min");
  // The field at the moment takes a while to work out.
  await expect(page.getByTestId("field-status")).toContainText("cells", { timeout: 60_000 });

  await expect(page.getByTestId("field-legend-quantity")).toHaveText("PAR (µmol/m²/s)");
  await expect(page.getByTestId("probe-1-reading")).toContainText(
    "PAR 362.93 µmol/m²/s, irradiance 168.97 W/m²",
  );
  await expect(page.getByTestId("probe-2-reading")).toContainText(
    "PAR 160.37 µmol/m²/s, irradiance 74.66 W/m²",
  );
  const weather = page.getByRole("region", { name: "Weather" });
  await weather.getByTestId("weather-summary").click();
  await expect(weather.getByTestId("weather-light")).toHaveText(
    "213 W/m², 48% of it the sky's, PAR 458 µmol/m²/s",
  );
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
