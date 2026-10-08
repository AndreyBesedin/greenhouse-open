import { describe, expect, it } from "vitest";

import {
  type CameraPasses,
  decodePasses,
  depthPicture,
  depthRange,
  instanceColor,
  instancePicture,
  passesAt,
} from "./passes";

// A pixel as the GPU writes it: a whole number in base 256 in red, green and
// blue, and full alpha; or nothing at all.
function written(code: number | null): number[] {
  return code === null
    ? [0, 0, 0, 0]
    : [code % 256, Math.floor(code / 256) % 256, Math.floor(code / 65536), 255];
}

// A 2 by 2 picture, read as WebGL reads it, from its bottom row up. Its top
// row shows the heater at 1.234 m, then nothing; its bottom row the floor at
// 70 m, then the heater at 2 m.
const INSTANCE = new Uint8Array([...written(2), ...written(1), ...written(1), ...written(null)]);
const DEPTH = new Uint8Array([
  ...written(70_000),
  ...written(2_000),
  ...written(1_234),
  ...written(null),
]);
const ENTITIES = ["heater", "floor"];

function decoded(): CameraPasses {
  return decodePasses(INSTANCE, DEPTH, 2, 2, ENTITIES);
}

describe("a camera's passes", () => {
  it("name each pixel's entity and depth, counted from the top left", () => {
    const passes = decoded();

    expect(passesAt(passes, 0, 0)).toEqual({ entityId: "heater", depth: 1.234 });
    expect(passesAt(passes, 1, 0)).toEqual({ entityId: null, depth: null });
    expect(passesAt(passes, 0, 1).entityId).toBe("floor");
    expect(passesAt(passes, 0, 1).depth).toBeCloseTo(70);
    expect(passesAt(passes, 1, 1)).toEqual({ entityId: "heater", depth: 2 });
  });

  it("read nothing beyond the picture", () => {
    expect(passesAt(decoded(), 2, 0)).toEqual({ entityId: null, depth: null });
    expect(passesAt(decoded(), 0, -1)).toEqual({ entityId: null, depth: null });
  });

  it("list the entities in view, those covering the most pixels first", () => {
    expect(decoded().inView).toEqual([
      { entityId: "heater", index: 0, pixels: 2 },
      { entityId: "floor", index: 1, pixels: 1 },
    ]);
  });

  it("leave out an entity the instance pass does not show", () => {
    const passes = decodePasses(INSTANCE, DEPTH, 2, 2, [...ENTITIES, "fan"]);

    expect(passes.inView.map((entry) => entry.entityId)).toEqual(["heater", "floor"]);
  });

  it("draw depth white at the nearest, black at the farthest and where nothing is", () => {
    const passes = decoded();
    const picture = depthPicture(passes);

    expect(depthRange(passes)).toEqual({ nearest: 1.234, farthest: 70 });
    // Top left, top right, bottom left: nearest, nothing, farthest.
    expect(Array.from(picture.slice(0, 12))).toEqual([
      255, 255, 255, 255, 0, 0, 0, 255, 0, 0, 0, 255,
    ]);
    // Bottom right, at 2 m: grey falls with the logarithm of depth.
    const grey = 1 - Math.log(2 / 1.234) / Math.log(70 / 1.234);
    expect(picture[12]).toBe(Math.round(grey * 255));
  });

  it("draw each entity in a colour of its own, and nothing in black", () => {
    const picture = instancePicture(decoded());

    expect(Array.from(picture.slice(0, 3))).toEqual(instanceColor(0));
    expect(Array.from(picture.slice(4, 8))).toEqual([0, 0, 0, 255]);
    expect(Array.from(picture.slice(8, 11))).toEqual(instanceColor(1));
    expect(instanceColor(0)).not.toEqual(instanceColor(1));
  });

  it("have no depth range when nothing is in view", () => {
    const empty = new Uint8Array(written(null));

    expect(depthRange(decodePasses(empty, empty, 1, 1, []))).toBeNull();
  });
});
