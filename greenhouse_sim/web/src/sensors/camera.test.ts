import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import {
  type CameraSpec,
  cameraOf,
  FRUSTUM_DEPTH_M,
  frustumOverlays,
  pixelAt,
  project,
} from "./camera";

const EXAMPLE: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../../public/scenes/example.json", import.meta.url), "utf8"),
);
// 60° across 640 pixels, as the simulator's tests take it
// (`tests/test_sensors.py`).
const FOCAL = 320 / Math.tan(Math.PI / 6);
// Level at 1 m, looking along x.
const LEVEL: CameraSpec = {
  cameraId: "level",
  eye: { x: 0, y: 0, z: 1 },
  target: { x: 10, y: 0, z: 1 },
  width: 640,
  height: 480,
  fx: FOCAL,
  fy: FOCAL,
  ppx: 320,
  ppy: 240,
};

describe("a camera's picture", () => {
  it("lands a known point on its known pixel, as the simulator projects it", () => {
    expect(project(LEVEL, { x: 10, y: 0, z: 1 })).toEqual({ u: 320, v: 240 });
    const left = project(LEVEL, { x: 10, y: 1, z: 1 });
    expect(left?.u).toBeCloseTo(320 - FOCAL / 10);
    expect(left?.v).toBeCloseTo(240);
    const up = project(LEVEL, { x: 10, y: 0, z: 2 });
    expect(up?.v).toBeCloseTo(240 - FOCAL / 10);
    expect(project(LEVEL, { x: -1, y: 0, z: 1 })).toBeNull();
  });

  it("shows, at each pixel, the point it projects there", () => {
    const point = pixelAt(LEVEL, 100, 400, 7);
    const back = project(LEVEL, point);

    expect(back?.u).toBeCloseTo(100);
    expect(back?.v).toBeCloseTo(400);
  });

  it("is read from the climate box's camera, which looks at its target", () => {
    const camera = EXAMPLE.entities.find((entity) => entity.kind === "CAMERA");
    const spec = camera === undefined ? null : cameraOf(camera);

    expect(spec?.cameraId).toBe("front_camera");
    expect(spec === null ? null : project(spec, spec.target)).toEqual({ u: 320, v: 240 });
    expect(cameraOf(EXAMPLE.entities[0] as never)).toBeNull();
  });
});

describe("a camera's frustum", () => {
  it("runs from its eye to its picture's corners, and around them", () => {
    const lines = frustumOverlays(EXAMPLE);
    const rays = lines.filter((line) => line.id.includes("-ray-"));

    expect(lines).toHaveLength(8);
    for (const ray of rays) {
      if (ray.kind !== "line") {
        throw new Error("a frustum is drawn in lines");
      }
      const reach = Math.hypot(ray.to.x - ray.from.x, ray.to.y - ray.from.y, ray.to.z - ray.from.z);
      expect(reach).toBeGreaterThan(FRUSTUM_DEPTH_M);
    }
  });
});
