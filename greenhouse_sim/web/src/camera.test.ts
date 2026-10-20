import { PerspectiveCamera, Vector3 } from "three";
import { describe, expect, it } from "vitest";

import {
  CAMERA_FIELD_OF_VIEW_DEG,
  CAMERA_PRESETS,
  type CameraPose,
  DEFAULT_PRESET,
  framing,
  PRESET_ORDER,
} from "./camera";
import { type Point3, worldToViewer } from "./world";

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

/** Where `point` appears in a view of `aspect` from `pose`, from -1 to 1
 * across and up the view where it is in it. */
function onTheView(pose: CameraPose, aspect: number, point: Point3): { x: number; y: number } {
  const camera = new PerspectiveCamera(CAMERA_FIELD_OF_VIEW_DEG, aspect);
  const position = worldToViewer(pose.position);
  const target = worldToViewer(pose.target);
  camera.position.set(position.x, position.y, position.z);
  camera.lookAt(target.x, target.y, target.z);
  camera.updateMatrixWorld();
  const seen = worldToViewer(point);
  const projected = new Vector3(seen.x, seen.y, seen.z).project(camera);
  return { x: projected.x, y: projected.y };
}

describe("a box framed", () => {
  // The reference greenhouse's bounds: 12 m by 9.6 m, 4.7 m to its ridge,
  // its footprint's middle at (6, 4.8).
  const base = { x: 6, y: 4.8, z: 0 };
  const size = { x: 12, y: 9.6, z: 4.7 };

  it.each([16 / 9, 1, 3 / 4])("is in view whole, at an aspect of %f", (aspect) => {
    const pose = framing(base, size, aspect);
    for (const dx of [-1, 1]) {
      for (const dy of [-1, 1]) {
        for (const z of [0, size.z]) {
          const corner = { x: base.x + (dx * size.x) / 2, y: base.y + (dy * size.y) / 2, z };
          const { x, y } = onTheView(pose, aspect, corner);
          expect(Math.abs(x)).toBeLessThanOrEqual(1);
          expect(Math.abs(y)).toBeLessThanOrEqual(1);
        }
      }
    }
  });

  it("is seen from the default preset's direction, aimed inside it, to a tenth of a metre", () => {
    const { position, target } = framing(base, size, 16 / 9);
    const away = CAMERA_PRESETS[DEFAULT_PRESET].position;
    const along = {
      x: position.x - target.x,
      y: position.y - target.y,
      z: position.z - target.z,
    };
    const length = Math.hypot(along.x, along.y, along.z);

    expect(target).toEqual({ x: 6, y: 4.8, z: 1.4 });
    for (const axis of ["x", "y", "z"] as const) {
      expect(along[axis] / length).toBeCloseTo(away[axis] / Math.hypot(away.x, away.y, away.z), 2);
      expect(Math.round(position[axis] * 10) / 10).toBe(position[axis]);
    }
  });
});
