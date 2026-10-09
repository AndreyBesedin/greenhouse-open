import { expect, test } from "@playwright/test";

import type { CameraPose } from "../src/camera.ts";
import { selectAt } from "./view";

function cameraText({ position, target }: CameraPose): string {
  return [position, target].map(({ x, y, z }) => `${x}:${y}:${z}`).join(",");
}

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

// The climate box's weather station stands on a mast 3 m in front of it: a
// point on its thermometer's face, seen from 1.5 m in front of it.
const STATION_FACE = { x: -3.04, y: 3.1, z: 1.5 };
const BEFORE_THE_STATION: CameraPose = {
  position: { x: -4.5, y: 3.1, z: 1.7 },
  target: STATION_FACE,
};

test("weather: the weather station reads the weather outside", async ({ page }) => {
  await page.goto(
    `/?scenario=climate_box&weather=cold_spring_day&field=climate&t=600&camera=${cameraText(BEFORE_THE_STATION)}`,
  );
  await expect(page.getByTestId("climate-time")).toHaveText("10 min", { timeout: 20_000 });

  await selectAt(page, STATION_FACE, "climate_box_station_temperature", BEFORE_THE_STATION);
  await expect(page.getByTestId("property-sensor_kind")).toHaveText("outside_temperature");
  // Its reading errs by its noise about the spring day's 7.95 °C.
  await expect(page.getByTestId("sensor-reading")).toHaveText("8.10 °C at 10 min");
  await expect(page.getByTestId("sensor-truth")).toHaveText("7.95 °C at 10 min");
});

test("weather: a recorded day replays from the run's start", async ({ page }) => {
  await page.goto("/?scenario=climate_box&field=climate&t=600");
  await expect(page.getByTestId("climate-time")).toHaveText("10 min", { timeout: 20_000 });
  const weather = page.getByRole("region", { name: "Weather" });
  await weather.getByTestId("weather-summary").click();
  await weather.getByRole("combobox", { name: "Weather to run under" }).selectOption({
    label: "example day",
  });

  // The file's record ten minutes past its midnight, played at the run's.
  await expect(page).toHaveURL(/weather=example_day/);
  await expect(weather.getByTestId("weather-summary")).toHaveText(
    "Outside at 1 Jan 2026, 00:10: 10.3 °C, wind 11.1 m/s from the SSW.",
  );
  await expect(weather.getByTestId("weather-pressure")).toHaveText("1008 hPa");
  await expect(weather.getByTestId("weather-day-day-temperature")).toHaveText(
    "Air, 8.8 to 13.4 °C",
  );
});
