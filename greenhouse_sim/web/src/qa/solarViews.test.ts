import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import { sceneSunlight } from "../weather/sunlight";
import { parseSolarLight, QA_SOLAR_VIEWS, qaSolarView, solarRange } from "./solarViews";

const LIGHT = parseSolarLight(
  JSON.parse(
    readFileSync(new URL("../../public/fields/qa-solar-lab-light.json", import.meta.url), "utf8"),
  ),
);
const SCENE: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../../public/scenes/qa-solar-lab.json", import.meta.url), "utf8"),
);

describe("the solar QA's views", () => {
  it("are the morning's, the noon's and the evening's, the noon's by default", () => {
    expect(qaSolarView("")).toBe("noon");
    expect(qaSolarView("?view=morning")).toBe("morning");
    expect(qaSolarView("?view=midnight")).toBeNull();
  });

  it("follow the sun across the equinox's sky, from the east by the south to the west", () => {
    const [morning, noon, evening] = QA_SOLAR_VIEWS.map((view) => LIGHT.views[view].weather.sun);

    expect(noon?.elevation_deg).toBeCloseTo(38.0, 1);
    expect(noon?.azimuth_deg).toBeCloseTo(180, 0);
    expect(morning?.azimuth_deg).toBeLessThan(180);
    expect(evening?.azimuth_deg).toBeGreaterThan(180);
    expect(morning?.elevation_deg).toBeLessThan(noon?.elevation_deg ?? 0);
    // Its path through the day, up from about seven to seven.
    expect(LIGHT.day.sun.filter((sun) => sun.elevation_deg > 0).length).toBeGreaterThan(60);
  });

  it("light the scene from the sun, and colour the floor on one scale", () => {
    for (const view of QA_SOLAR_VIEWS) {
      expect(sceneSunlight(SCENE, LIGHT.views[view].weather)).toMatchObject({
        target: { x: 6, y: 3.2 },
      });
    }
    const range = solarRange(LIGHT);
    expect(range.min).toBe(0);
    expect(range.max).toBe(LIGHT.views.noon.field.channels.par?.maximum);
    expect(range.max).toBeGreaterThan(1000);
  });

  it("are checked rather than trusted", () => {
    expect(() => parseSolarLight({ views: {}, day: {} })).toThrow("has no morning");
    expect(() => parseSolarLight(null)).toThrow("not what the viewer expects");
  });
});
