import { describe, expect, it } from "vitest";

import { CAMERA_PRESETS, DEFAULT_PRESET, PRESET_ORDER } from "./camera";
import type { Point3 } from "./world";

const VIEW_DISTANCE_M = 9;

function distance(a: Point3, b: Point3): number {
  return Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
}

describe("camera presets", () => {
  it("offers top, front, side and isometric, and starts isometric", () => {
    expect(PRESET_ORDER).toEqual(["top", "front", "side", "isometric"]);
    expect(DEFAULT_PRESET).toBe("isometric");
  });

  it.each(PRESET_ORDER)("%s looks at the origin from the same distance", (preset) => {
    const { position, target } = CAMERA_PRESETS[preset];

    expect(target).toEqual({ x: 0, y: 0, z: 0 });
    expect(distance(position, target)).toBeCloseTo(VIEW_DISTANCE_M, 2);
  });

  it("top looks straight down, leaning just enough to keep +y up the screen", () => {
    const { position } = CAMERA_PRESETS.top;

    expect(position.x).toBe(0);
    expect(position.y).toBeLessThan(0);
    expect(position.y).toBeGreaterThan(-0.01);
    expect(position.z).toBeCloseTo(VIEW_DISTANCE_M);
  });

  it("front looks along +y and side along -x, both level with the ground", () => {
    expect(CAMERA_PRESETS.front.position).toEqual({ x: 0, y: -VIEW_DISTANCE_M, z: 0 });
    expect(CAMERA_PRESETS.side.position).toEqual({ x: VIEW_DISTANCE_M, y: 0, z: 0 });
  });

  it("isometric is equally far along each axis, from the front-right-top", () => {
    const { x, y, z } = CAMERA_PRESETS.isometric.position;

    expect(x).toBeGreaterThan(0);
    expect(-y).toBeCloseTo(x);
    expect(z).toBeCloseTo(x);
  });
});
