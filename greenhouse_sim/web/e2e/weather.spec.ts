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

test("weather: a scenario runs under a preset day, charted through the day", async ({ page }) => {
  await page.goto("/?scenario=climate_box&field=climate&t=600");
  await expect(page.getByTestId("climate-time")).toHaveText("10 min", { timeout: 20_000 });
  const weather = page.getByRole("region", { name: "Weather" });
  await expect(weather.getByTestId("weather-summary")).toHaveText(
    "Outside at 1 Jan 2026, 00:10: 8.0 °C, wind calm.",
  );

  await weather.getByTestId("weather-summary").click();
  await weather.getByRole("combobox", { name: "Weather to run under" }).selectOption({
    label: "cold spring day",
  });

  await expect(page).toHaveURL(/weather=cold_spring_day/);
  // Ten minutes past midnight on the spring day: cooling towards dawn, the
  // wind from the south-west, gusting.
  await expect(weather.getByTestId("weather-summary")).toHaveText(
    "Outside at 1 Jan 2026, 00:10: 7.9 °C, wind 3.5 m/s from the SW.",
  );
  await expect(weather.getByTestId("weather-day-day-temperature")).toHaveText(
    "Air, 4.0 to 16.0 °C",
  );
  await expect(weather.getByTestId("weather-day-day-humidity")).toHaveText(
    "Humidity, 42.5 to 95.0 %",
  );
  await expect(weather.getByTestId("weather-day-now")).toHaveCount(3);
  // The run carries on at the same moment, under the new weather.
  await expect(page.getByTestId("climate-time")).toHaveText("10 min", { timeout: 20_000 });

  await weather.getByRole("combobox", { name: "Weather to run under" }).selectOption({
    label: "its own",
  });
  await expect(page).not.toHaveURL(/weather=/);
  await expect(weather.getByTestId("weather-day-day-temperature")).toHaveText("Air, 8.0 °C");
});
