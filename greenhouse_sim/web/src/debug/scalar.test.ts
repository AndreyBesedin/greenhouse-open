import { readFileSync } from "node:fs";

import { SRGBColorSpace, Color as ThreeColor } from "three";
import { describe, expect, it } from "vitest";

import type { Color, SceneSnapshot } from "../scene/generated/snapshotTypes";
import { colouringBy, SCALAR_STOPS, scalarColor, scalarPosition, scalarProperties } from "./scalar";

const EXAMPLE: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../../public/scenes/example.json", import.meta.url), "utf8"),
);
const LAST = SCALAR_STOPS.length - 1;

function stop(index: number): Color {
  const { r, g, b } = new ThreeColor(SCALAR_STOPS[index]).getRGB(new ThreeColor(), SRGBColorSpace);
  return { r, g, b };
}

function expectColor(actual: Color, expected: Color): void {
  expect(actual.r).toBeCloseTo(expected.r);
  expect(actual.g).toBeCloseTo(expected.g);
  expect(actual.b).toBeCloseTo(expected.b);
}

describe("shading entities by a property", () => {
  it("offers the numeric properties of the scene's entities", () => {
    expect(scalarProperties(EXAMPLE)).toEqual([
      "age_days",
      "aperture_m2",
      "cumulative_harvest_g",
      "diameter_m",
      "flow_m3_s",
      "fruits_on_plant",
      "heat_w",
      "level",
      "open_fraction",
      "position_in_row",
      "power_w",
      "removal_kg_h",
      "ripe_fruits",
      "row",
      "trusses",
      "visible_height_cm",
    ]);
  });

  it("spans the values the scene holds", () => {
    // The example's 32 plants carry 3 to 6 fruit each on day 9.
    expect(colouringBy(EXAMPLE, "fruits_on_plant")).toEqual({
      property: "fruits_on_plant",
      range: { min: 3, max: 6 },
    });
    expect(colouringBy(EXAMPLE, "no_such_property")).toBeNull();
  });

  it("colours the ends of the range with the scale's ends, and clamps beyond them", () => {
    const range = { min: 10, max: 15 };

    expectColor(scalarColor(10, range), stop(0));
    expectColor(scalarColor(15, range), stop(LAST));
    expectColor(scalarColor(-3, range), stop(0));
    expectColor(scalarColor(99, range), stop(LAST));
  });

  it("puts a range of one value in the middle of the scale", () => {
    expect(scalarPosition(3, { min: 3, max: 3 })).toBe(0.5);
    expectColor(scalarColor(3, { min: 3, max: 3 }), stop(LAST / 2));
  });

  it("blends neighbouring colours in between", () => {
    // An eighth of the way along five colours is halfway from the first to the second.
    const first = stop(0);
    const second = stop(1);

    expectColor(scalarColor(1, { min: 0, max: 8 }), {
      r: (first.r + second.r) / 2,
      g: (first.g + second.g) / 2,
      b: (first.b + second.b) / 2,
    });
  });
});
