import { expect, type Page, test } from "@playwright/test";

import type { CameraPose } from "../src/camera.ts";
import { selectAt } from "./view";

/**
 * P07's final QA, `weather-day`: the climate box through the cold spring
 * day, replayed at the runtime. The outside changes through the day, the
 * air inside answers it in the field and the whole house, the side vents'
 * flows turn with the wind, the sensors and the weather station report the
 * changes, a controlled run pulls away from the same day all off, and the
 * replay is the same every time.
 */

const H = 3600;
const DAY = "/?scenario=climate_box&weather=cold_spring_day&field=climate&probes=6:3.2:1.5";
// Heated until eight and from six; the roof vent half open and the fan on
// from eleven to four (as `tests/test_controlled_day.py` runs it).
const CONTROLLED = `${DAY}&set=heater:1&schedule=${[
  "28800:heater:0",
  "39600:roof_vent:0.5",
  "39600:fan:1",
  "57600:roof_vent:0",
  "57600:fan:0",
  "64800:heater:1",
].join(",")}`;
const ACROSS = `${DAY}&open=side_vent:1,side_vent_left:1`;
// The front thermometer, inside, and the weather station's, on its mast in
// front of the house: a point on each one's face, and a camera before it.
const FRONT_FACE = { x: 3.04, y: 3.1, z: 1.5 };
const BESIDE_THE_FRONT: CameraPose = { position: { x: 4.5, y: 3.1, z: 1.7 }, target: FRONT_FACE };
const STATION_FACE = { x: -3.04, y: 3.1, z: 1.5 };
const BEFORE_THE_STATION: CameraPose = {
  position: { x: -4.5, y: 3.1, z: 1.7 },
  target: STATION_FACE,
};
const ARRIVES = { timeout: 90_000 };

function cameraText({ position, target }: CameraPose): string {
  return [position, target].map(({ x, y, z }) => `${x}:${y}:${z}`).join(",");
}

async function at(page: Page, address: string, seconds: number, shown: string): Promise<void> {
  await page.goto(`${address}&t=${seconds}`);
  await expect(page.getByTestId("climate-time")).toHaveText(shown, ARRIVES);
}

async function sensorReads(
  page: Page,
  address: string,
  seconds: number,
  shown: string,
  face: typeof FRONT_FACE,
  pose: CameraPose,
  entityId: string,
): Promise<string> {
  await at(page, `${address}&camera=${cameraText(pose)}`, seconds, shown);
  await selectAt(page, face, entityId, pose);
  const reading = page.getByRole("region", { name: "Sensor" }).getByTestId("sensor-reading");
  await expect(reading).toHaveText(new RegExp(`at ${shown}$`), ARRIVES);
  return (await reading.textContent()) ?? "";
}

test("weather-day: the climate box through a cold spring day", async ({ page }) => {
  test.setTimeout(600_000);
  const weather = page.getByRole("region", { name: "Weather" });
  const house = page.getByRole("figure", { name: "House air" });
  const probe = page.getByTestId("probe-1-reading");

  await test.step("the outside changes through the day", async () => {
    await at(page, DAY, 6 * H, "6 h 00 min");
    await expect(weather.getByTestId("weather-summary")).toHaveText(
      "Outside at 1 Jan 2026, 06:00: 4.0 °C, wind 1.9 m/s from the WSW.",
    );
    await weather.getByTestId("weather-summary").click();
    await expect(weather.getByTestId("weather-day-day-temperature")).toHaveText(
      "Air, 4.0 to 16.0 °C",
    );
    await at(page, DAY, 15 * H, "15 h 00 min");
    await expect(weather.getByTestId("weather-summary")).toHaveText(
      "Outside at 1 Jan 2026, 15:00: 16.0 °C, wind 5.1 m/s from the WNW.",
    );
  });

  await test.step("the air inside answers it, in the field and the whole house", async () => {
    await at(page, DAY, 6 * H, "6 h 00 min");
    await expect(house.getByTestId("house-air-°C")).toHaveText("Air 4.0 °C, all off 4.0 °C");
    await expect(probe).toHaveText(/temperature [34]\.\d\d °C/, ARRIVES);
    await at(page, DAY, 15 * H, "15 h 00 min");
    await expect(house.getByTestId("house-air-°C")).toHaveText("Air 16.0 °C, all off 16.0 °C");
    await expect(probe).toHaveText(/temperature 1[56]\.\d\d °C/, ARRIVES);
  });

  await test.step("the side vents' flows turn with the wind", async () => {
    const inThrough = async (seconds: number) => {
      const response = await page.request.get(
        `/api/scenarios/climate_box/climate/openings?open=side_vent:1,side_vent_left:1&weather=cold_spring_day&t=${seconds}`,
      );
      const body = (await response.json()) as {
        openings: { opening_id: string; net_m3_s: number }[];
      };
      return body.openings.filter((o) => o.net_m3_s > 0).map((o) => o.opening_id);
    };
    // From the south-west after midnight: in on the south side.
    await at(page, ACROSS, 600, "10 min");
    await expect(page.getByTestId("debug-label")).toContainText(
      ["2.06 m³/s in", "2.06 m³/s out"],
      ARRIVES,
    );
    expect(await inThrough(600)).toEqual(["side_vent"]);
    // From the west-north-west by evening: in on the north side.
    await at(page, ACROSS, 20 * H, "20 h 00 min");
    await expect(page.getByTestId("debug-label")).toContainText(
      ["2.24 m³/s out", "2.24 m³/s in"],
      ARRIVES,
    );
    expect(await inThrough(20 * H)).toEqual(["side_vent_left"]);
  });

  await test.step("the sensors report the changes inside, the station those outside", async () => {
    const id = "climate_box_temperature_front";
    const station = "climate_box_station_temperature";
    expect(
      await sensorReads(page, DAY, 6 * H, "6 h 00 min", FRONT_FACE, BESIDE_THE_FRONT, id),
    ).toBe("4.00 °C at 6 h 00 min");
    expect(
      await sensorReads(page, DAY, 15 * H, "15 h 00 min", FRONT_FACE, BESIDE_THE_FRONT, id),
    ).toBe("16.00 °C at 15 h 00 min");
    expect(
      await sensorReads(page, DAY, 6 * H, "6 h 00 min", STATION_FACE, BEFORE_THE_STATION, station),
    ).toBe("3.90 °C at 6 h 00 min");
    expect(
      await sensorReads(
        page,
        DAY,
        15 * H,
        "15 h 00 min",
        STATION_FACE,
        BEFORE_THE_STATION,
        station,
      ),
    ).toBe("15.90 °C at 15 h 00 min");
  });

  await test.step("a controlled run pulls away from the same day all off", async () => {
    await at(page, CONTROLLED, 20 * H, "20 h 00 min");
    await expect(house.getByTestId("house-air-°C")).toHaveText("Air 19.9 °C, all off 13.1 °C");
  });

  await test.step("played, it moves on through the day", async () => {
    const run = page.getByRole("group", { name: "Climate run" });
    await run.getByRole("button", { name: "Play" }).click();
    await expect(page.getByTestId("climate-time")).toHaveText("20 h 05 min", ARRIVES);
    await run.getByRole("button", { name: "Pause" }).click();
  });

  await test.step("the replay is the same every time", async () => {
    await at(page, CONTROLLED, 20 * H, "20 h 00 min");
    const first = [
      await house.getByTestId("house-air-°C").textContent(),
      await probe.textContent(),
    ];
    await page.reload();
    await expect(page.getByTestId("climate-time")).toHaveText("20 h 00 min", ARRIVES);
    await expect(house.getByTestId("house-air-°C")).toHaveText(first[0] ?? "");
    await expect(probe).toHaveText(first[1] ?? "", ARRIVES);
  });
});
