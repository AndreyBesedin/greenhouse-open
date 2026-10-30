import { describe, expect, it } from "vitest";

import { CANOPY_CLEAREST, CANOPY_DENSEST, canopyOpacity } from "./canopy";
import type { SceneEntity } from "./generated/snapshotTypes";

function canopy(properties: SceneEntity["properties"]): SceneEntity {
  return {
    entity_id: "row_1_canopy",
    kind: "CANOPY",
    transform: { position: { x: 0, y: 0, z: 0 }, rotation: { x: 0, y: 0, z: 0, w: 1 } },
    shape: { shape: "box", size_x: 10, size_y: 1.6, size_z: 2 },
    color: { r: 0.36, g: 0.66, b: 0.3 },
    material: null,
    label: "row_1 canopy (a proxy)",
    properties,
  };
}

describe("a canopy drawn as dense as the light its leaves take (decision 0062)", () => {
  it("goes from its clearest to its densest as its density goes from 0 to 1", () => {
    expect(canopyOpacity(canopy({ density: 0 }))).toBe(CANOPY_CLEAREST);
    expect(canopyOpacity(canopy({ density: 1 }))).toBe(CANOPY_DENSEST);
    expect(canopyOpacity(canopy({ density: 0.5 }))).toBeCloseTo(
      (CANOPY_CLEAREST + CANOPY_DENSEST) / 2,
      12,
    );
  });

  it("takes a density out of range at its nearest bound, and one not a number at its clearest", () => {
    expect(canopyOpacity(canopy({}))).toBe(CANOPY_CLEAREST);
    expect(canopyOpacity(canopy({ density: "dense" }))).toBe(CANOPY_CLEAREST);
    expect(canopyOpacity(canopy({ density: -0.2 }))).toBe(CANOPY_CLEAREST);
    expect(canopyOpacity(canopy({ density: 1.4 }))).toBe(CANOPY_DENSEST);
    expect(canopyOpacity(canopy({ density: Number.NaN }))).toBe(CANOPY_CLEAREST);
  });
});
