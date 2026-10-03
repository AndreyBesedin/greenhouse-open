import { Euler, Vector3 } from "three";
import { describe, expect, it } from "vitest";

import { WORLD_TO_VIEWER_ROTATION, worldToViewer } from "./world";

describe("drawing the z-up world in Three.js's y-up axes", () => {
  it.each([
    ["world up becomes screen up", { x: 0, y: 0, z: 1 }, { x: 0, y: 1, z: 0 }],
    ["world x stays x", { x: 1, y: 0, z: 0 }, { x: 1, y: 0, z: 0 }],
    ["world y points into the screen", { x: 0, y: 1, z: 0 }, { x: 0, y: 0, z: -1 }],
  ])("%s", (_, world, viewer) => {
    const drawn = worldToViewer(world);

    expect(drawn.x).toBeCloseTo(viewer.x);
    expect(drawn.y).toBeCloseTo(viewer.y);
    expect(drawn.z).toBeCloseTo(viewer.z);
  });

  it("is exactly what the scene's root rotation does", () => {
    const point = { x: 1.5, y: -2, z: 3 };
    const rotated = new Vector3(point.x, point.y, point.z).applyEuler(
      new Euler(...WORLD_TO_VIEWER_ROTATION),
    );
    const expected = worldToViewer(point);

    expect(rotated.x).toBeCloseTo(expected.x);
    expect(rotated.y).toBeCloseTo(expected.y);
    expect(rotated.z).toBeCloseTo(expected.z);
  });

  it("keeps the axes right-handed", () => {
    const x = new Vector3(1, 0, 0).applyEuler(new Euler(...WORLD_TO_VIEWER_ROTATION));
    const y = new Vector3(0, 1, 0).applyEuler(new Euler(...WORLD_TO_VIEWER_ROTATION));
    const z = new Vector3(0, 0, 1).applyEuler(new Euler(...WORLD_TO_VIEWER_ROTATION));

    expect(x.clone().cross(y).distanceTo(z)).toBeCloseTo(0);
  });
});
