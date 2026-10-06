import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import type { SceneEntity, SceneSnapshot } from "../scene/generated/snapshotTypes";
import { sceneDimensionOverlays } from "./dimensions";
import { entityBounds } from "./overlays";

const EXAMPLE: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../../public/scenes/example.json", import.meta.url), "utf8"),
);
const BOUNDS = EXAMPLE.entities.find(
  (entity) => entity.kind === "GREENHOUSE_BOUNDS",
) as SceneEntity;
// A quarter turn about z: the greenhouse's length runs along the world's y.
const QUARTER_TURN = Math.SQRT1_2;

function labels(snapshot: SceneSnapshot): string[] {
  return sceneDimensionOverlays(snapshot).flatMap((primitive) =>
    primitive.kind === "label" ? [primitive.text] : [],
  );
}

describe("measuring a scene", () => {
  it("labels the greenhouse's length, width and height, and the world's axes", () => {
    expect(labels(EXAMPLE)).toEqual([
      "x",
      "y",
      "z",
      "length 4.00 m",
      "width 6.40 m",
      "height 3.65 m",
    ]);
  });

  it("measures along the edges from the greenhouse's floor corner", () => {
    const lines = sceneDimensionOverlays(EXAMPLE).filter((primitive) => primitive.kind === "line");

    expect(lines.map((line) => line.kind === "line" && [line.from, line.to])).toEqual([
      [
        { x: 0, y: expect.closeTo(0), z: 0 },
        { x: 4, y: expect.closeTo(0), z: 0 },
      ],
      [
        { x: 0, y: expect.closeTo(0), z: 0 },
        { x: 0, y: expect.closeTo(6.4), z: 0 },
      ],
      [
        { x: 0, y: expect.closeTo(0), z: 0 },
        { x: 0, y: expect.closeTo(0), z: 3.65 },
      ],
    ]);
  });

  it("turns with a greenhouse that is turned in the world", () => {
    const turned: SceneSnapshot = {
      ...EXAMPLE,
      entities: [
        {
          ...BOUNDS,
          transform: {
            position: { x: 0, y: 0, z: 0 },
            rotation: { w: QUARTER_TURN, x: 0, y: 0, z: QUARTER_TURN },
          },
        },
      ],
    };
    const [length] = sceneDimensionOverlays(turned);

    expect(length?.kind === "line" && length.to.y - length.from.y).toBeCloseTo(4);
    expect(length?.kind === "line" && length.to.x - length.from.x).toBeCloseTo(0);
  });

  it("gives every primitive its own identifier", () => {
    const ids = sceneDimensionOverlays(EXAMPLE).map((primitive) => primitive.id);

    expect(new Set(ids).size).toBe(ids.length);
  });

  it("finds a box's bounds from its base up", () => {
    expect(entityBounds(BOUNDS)).toEqual({
      min: { x: 0, y: expect.closeTo(0), z: 0 },
      max: { x: 4, y: expect.closeTo(6.4), z: 3.65 },
    });
  });
});
