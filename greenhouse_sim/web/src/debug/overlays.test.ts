import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import type { SceneEntity, SceneSnapshot } from "../scene/generated/snapshotTypes";
import { sceneDimensionOverlays } from "./dimensions";
import { entityBounds, type OverlayToggles, selectionOverlays } from "./overlays";
import { colouringBy, scalarColor, scalarProperties, scalarValue } from "./scalar";

const EXAMPLE_JSON = readFileSync(
  new URL("../../public/scenes/example.json", import.meta.url),
  "utf8",
);
const EXAMPLE: SceneSnapshot = JSON.parse(EXAMPLE_JSON);

function entity(entityId: string): SceneEntity {
  const found = EXAMPLE.entities.find((candidate) => candidate.entity_id === entityId);
  if (found === undefined) {
    throw new Error(`no ${entityId} in the example scene`);
  }
  return found;
}

const PLANT = entity("climate_box_plant_001");
// The example scene's first plant stands on its gutter's slab, 0.675 m up, at
// the first row's first place; its stem is 0.35 m tall and 0.02 m in radius.
const BASE = { x: 2.25, y: 2.4, z: 0.675 };
const STEM_M = 0.3499;
const RADIUS_M = 0.02;
// A quarter turn about +x tips the plant's +z over onto -y.
const QUARTER_TURN = Math.SQRT1_2;
const TIPPED: SceneEntity = {
  ...PLANT,
  transform: { ...PLANT.transform, rotation: { w: QUARTER_TURN, x: QUARTER_TURN, y: 0, z: 0 } },
};
const EVERY_TOGGLE: OverlayToggles[] = [false, true].flatMap((box) =>
  [false, true].flatMap((axes) => [false, true].map((label) => ({ box, axes, label }))),
);

function deepFreeze<T>(value: T): T {
  if (typeof value === "object" && value !== null) {
    for (const child of Object.values(value)) {
      deepFreeze(child);
    }
    Object.freeze(value);
  }
  return value;
}

describe("an entity's bounding box", () => {
  it("holds an upright stem from its base to its top", () => {
    const { min, max } = entityBounds(PLANT);

    expect(min.x).toBeCloseTo(BASE.x - RADIUS_M);
    expect(max.x).toBeCloseTo(BASE.x + RADIUS_M);
    expect(min.y).toBeCloseTo(BASE.y - RADIUS_M);
    expect(max.y).toBeCloseTo(BASE.y + RADIUS_M);
    expect(min.z).toBeCloseTo(BASE.z);
    expect(max.z).toBeCloseTo(BASE.z + STEM_M);
  });

  it("follows the entity's rotation", () => {
    const { min, max } = entityBounds(TIPPED);

    // The stem now lies along -y, and its radius spans z.
    expect(min.y).toBeCloseTo(BASE.y - STEM_M);
    expect(max.y).toBeCloseTo(BASE.y);
    expect(min.z).toBeCloseTo(BASE.z - RADIUS_M);
    expect(max.z).toBeCloseTo(BASE.z + RADIUS_M);
  });

  it("is flat for the floor and a wall, follows a gable's corners, and spans the axes marker", () => {
    expect(entityBounds(entity("climate_box_end_wall_front"))).toEqual({
      min: { x: expect.closeTo(0), y: expect.closeTo(0), z: expect.closeTo(0) },
      max: { x: expect.closeTo(0), y: expect.closeTo(6.4), z: expect.closeTo(4.8) },
    });
    expect(entityBounds(entity("climate_box_floor"))).toEqual({
      min: { x: 0, y: expect.closeTo(0), z: 0 },
      max: { x: 12, y: expect.closeTo(6.4), z: 0 },
    });
    expect(entityBounds(entity("climate_box_side_wall_right"))).toEqual({
      min: { x: 0, y: expect.closeTo(0), z: expect.closeTo(0) },
      max: { x: 12, y: expect.closeTo(0), z: expect.closeTo(4) },
    });
    expect(entityBounds(entity("climate_box_axes"))).toEqual({
      min: { x: 0, y: 0, z: 0 },
      max: { x: 1, y: 1, z: 1 },
    });
  });
});

describe("the overlays around a selection", () => {
  it("draw the box, the origin and axes, and the label, each when it is on", () => {
    const ids = (toggles: OverlayToggles) => selectionOverlays(PLANT, toggles).map((p) => p.id);

    expect(ids({ box: true, axes: true, label: true })).toEqual([
      "box",
      "origin",
      "axis-x",
      "axis-y",
      "axis-z",
      "leader",
      "label",
    ]);
    expect(ids({ box: false, axes: true, label: false })).toEqual([
      "origin",
      "axis-x",
      "axis-y",
      "axis-z",
    ]);
    expect(ids({ box: false, axes: false, label: false })).toEqual([]);
  });

  it("show the entity's own axes, turned as it is turned", () => {
    const axisZ = selectionOverlays(TIPPED, { box: false, axes: true, label: false }).find(
      (primitive) => primitive.id === "axis-z",
    );

    expect(axisZ).toMatchObject({
      kind: "arrow",
      origin: { x: BASE.x, y: BASE.y, z: expect.closeTo(BASE.z) },
    });
    expect(axisZ?.kind === "arrow" && axisZ.direction).toEqual({
      x: 0,
      y: expect.closeTo(-1),
      z: expect.closeTo(0),
    });
  });

  it("label the entity above its top, on a leader line", () => {
    const [leader, label] = selectionOverlays(PLANT, { box: false, axes: false, label: true });

    expect(leader).toMatchObject({ kind: "line", from: { z: expect.closeTo(BASE.z + STEM_M) } });
    expect(label).toMatchObject({ kind: "label", text: "climate_box_plant_001" });
    expect(label?.kind === "label" && label.position.z).toBeGreaterThan(BASE.z + STEM_M);
  });

  it("never change the scene they explain, nor do dimensions or colourings", () => {
    const scene = deepFreeze(JSON.parse(EXAMPLE_JSON) as SceneSnapshot);

    for (const toggles of EVERY_TOGGLE) {
      for (const shown of scene.entities) {
        selectionOverlays(shown, toggles);
      }
    }
    sceneDimensionOverlays(scene);
    for (const property of scalarProperties(scene)) {
      const colouring = colouringBy(scene, property);
      for (const shown of scene.entities) {
        const value = scalarValue(shown, property);
        if (colouring !== null && value !== null) {
          scalarColor(value, colouring.range);
        }
      }
    }

    expect(scene).toEqual(JSON.parse(EXAMPLE_JSON));
  });
});
