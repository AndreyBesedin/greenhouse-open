import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import type { Point3 } from "../world";
import { sceneSunlight, sunLightPose, sunPathOverlays } from "./sunlight";
import type { SunPosition, WeatherAtAMoment, WeatherDay } from "./weather";

const EXAMPLE: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../../public/scenes/example.json", import.meta.url), "utf8"),
);
// The example's house: 12 m by 6.4 m and 4.8 m high, its middle here.
const MIDDLE = { x: 6, y: 3.2, z: 2.4 };
const HALF_DIAGONAL_M = Math.hypot(12, 6.4, 4.8) / 2;

/** The unit vector towards a sun at a bearing and an elevation, x east and
 * y north. */
function towards(azimuthDeg: number, elevationDeg: number): Point3 {
  const azimuth = (azimuthDeg * Math.PI) / 180;
  const elevation = (elevationDeg * Math.PI) / 180;
  return {
    x: Math.sin(azimuth) * Math.cos(elevation),
    y: Math.cos(azimuth) * Math.cos(elevation),
    z: Math.sin(elevation),
  };
}

function weatherWith(sun: SunPosition): WeatherAtAMoment {
  return {
    site: {
      latitude_deg: 52,
      longitude_deg: 4.5,
      elevation_m: 0,
      time_zone: "Europe/Amsterdam",
      x_bearing_deg: 90,
    },
    moment: "2026-03-20T07:00:00Z",
    timeS: 0,
    weather: {
      air_temperature_c: 8,
      relative_humidity_pct: 80,
      co2_ppm: 420,
      wind_speed_m_s: 0,
      wind_direction_deg: null,
      barometric_pressure_hpa: 1013.25,
      global_radiation_w_m2: 0,
      cloud_cover_pct: 0,
    },
    windMS: { x: 0, y: 0, z: 0 },
    light: { ghi_w_m2: 0, dni_w_m2: 0, dhi_w_m2: 0, par_umol_m2_s: 0 },
    sun,
    sunDirection: towards(sun.azimuth_deg, sun.elevation_deg),
  };
}

describe("the sun's light", () => {
  it("shines at the house's middle from beyond it, its shadows covering it", () => {
    const pose = sunLightPose(EXAMPLE, towards(180, 30));

    expect(pose?.target).toEqual(MIDDLE);
    // Twice the house's longer side away, to the south and up.
    expect(pose?.distanceM).toBeCloseTo(24);
    expect(pose?.position.y).toBeCloseTo(MIDDLE.y - 24 * Math.cos(Math.PI / 6));
    expect(pose?.position.z).toBeCloseTo(MIDDLE.z + 12);
    expect(pose?.shadowHalfWidthM).toBeGreaterThan(HALF_DIAGONAL_M);
  });

  it("comes from the east in the morning and the west in the evening", () => {
    const morning = sunLightPose(EXAMPLE, towards(100, 10));
    const evening = sunLightPose(EXAMPLE, towards(260, 10));

    expect(morning?.position.x).toBeGreaterThan(MIDDLE.x);
    expect(evening?.position.x).toBeLessThan(MIDDLE.x);
    expect((morning?.position.x ?? 0) - MIDDLE.x).toBeCloseTo(
      MIDDLE.x - (evening?.position.x ?? 0),
    );
  });

  it("lights the scene while the sun is up, and leaves it to the sky at night", () => {
    const day = sceneSunlight(EXAMPLE, weatherWith({ elevation_deg: 30, azimuth_deg: 180 }));
    const night = sceneSunlight(EXAMPLE, weatherWith({ elevation_deg: -10, azimuth_deg: 0 }));

    expect(day).toMatchObject({ target: MIDDLE });
    expect(night).toBe("night");
  });

  it("is the viewer's fixed light in a scene without the house's bounds", () => {
    const open = {
      ...EXAMPLE,
      entities: EXAMPLE.entities.filter((entity) => entity.kind !== "GREENHOUSE_BOUNDS"),
    };

    expect(sunLightPose(open, towards(180, 30))).toBeNull();
    expect(sceneSunlight(open, weatherWith({ elevation_deg: -10, azimuth_deg: 0 }))).toBeNull();
    expect(
      sunPathOverlays(open, {
        start: "",
        timesS: [],
        weather: [],
        sun: [],
        sunDirections: [],
      }),
    ).toEqual([]);
  });
});

describe("the sun's path", () => {
  // Hourly from six to six: up from seven to five, from the east round by
  // the south to the west.
  const hours = [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18];
  const sun = hours.map((hour) => ({
    elevation_deg: hour <= 6 || hour >= 18 ? -5 : 38 - Math.abs(hour - 12) * 6,
    azimuth_deg: 90 + (hour - 6) * 15,
  }));
  const day = {
    sun,
    sunDirections: sun.map((at) => towards(at.azimuth_deg, at.elevation_deg)),
    timesS: hours.map((hour) => hour * 3600),
  } as unknown as WeatherDay;

  it("joins the sun's positions while it is up, at its marker's reach", () => {
    const lines = sunPathOverlays(EXAMPLE, day);

    // Eleven hours up, ten lines between them.
    expect(lines).toHaveLength(10);
    const first = lines[0];
    const last = lines.at(-1);
    if (first?.kind === "line" && last?.kind === "line") {
      expect(first.from.x).toBeGreaterThan(MIDDLE.x);
      expect(last.to.x).toBeLessThan(MIDDLE.x);
      const reach = Math.hypot(
        first.from.x - MIDDLE.x,
        first.from.y - MIDDLE.y,
        first.from.z - MIDDLE.z,
      );
      expect(reach).toBeCloseTo(18);
    }
    expect(lines.every((line) => line.kind === "line" && line.from.z > MIDDLE.z)).toBe(true);
  });
});
