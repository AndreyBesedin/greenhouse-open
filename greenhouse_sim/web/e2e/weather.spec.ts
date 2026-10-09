import { expect, test } from "@playwright/test";

test("weather: a scenario's panel shows the weather outside it, and its site", async ({ page }) => {
  await page.goto("/?scenario=tomato_compartment");
  const weather = page.getByRole("region", { name: "Weather" });

  // Its runs start at midnight at the site: 23:00 UTC is midnight in Amsterdam.
  await expect(weather.getByTestId("weather-summary")).toHaveText(
    "Outside at 1 Jan 2026, 00:00: 10.0 °C, wind 4.0 m/s from the SW.",
  );
  // Opened, its details.
  await weather.getByTestId("weather-summary").click();
  await expect(weather.getByTestId("weather-air")).toHaveText("10.0 °C, 80% RH, 420 ppm CO₂");
  await expect(weather.getByTestId("weather-wind")).toHaveText("4.0 m/s from the SW (225°)");
  await expect(weather.getByTestId("weather-pressure")).toBeVisible();
  await expect(weather.getByTestId("weather-pressure")).toHaveText("1013 hPa");
  await expect(weather.getByTestId("weather-site")).toHaveText(
    "52.00° N, 4.50° E, Europe/Amsterdam; x points E",
  );
  // The needle along the way it blows: to the north-east.
  await expect(weather.getByTestId("wind-needle")).toHaveAttribute("transform", "rotate(45 16 16)");
});

test("weather: the panel follows a climate run's moment, in a calm", async ({ page }) => {
  await page.goto("/?scenario=climate_box&field=climate&t=600");
  await expect(page.getByTestId("climate-time")).toHaveText("10 min", { timeout: 20_000 });
  const weather = page.getByRole("region", { name: "Weather" });

  await expect(weather.getByTestId("weather-summary")).toHaveText(
    "Outside at 1 Jan 2026, 00:10: 8.0 °C, wind calm.",
  );
  await expect(weather.getByTestId("wind-needle")).toHaveCount(0);
});
