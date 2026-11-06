// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { act } from "react";
import { PerspectiveCamera, Vector3 } from "three";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CAMERA_FIELD_OF_VIEW_DEG, type CameraPose } from "../camera";
import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import { button, click, type Rendered, render } from "../testing/render";
import { type Point3, worldToViewer } from "../world";

// The simulator's first draft of the form's starting house, as it answers it.
const STARTING_HOUSE = JSON.parse(
  readFileSync(join(process.cwd(), "src/builder/testing/startingHouse.json"), "utf8"),
);

// A long house, 40 m by 9.6 m and 4.7 m to its ridge, as the scene bounds it:
// the middle of its floor and its size.
const BASE = { x: 20, y: 4.8, z: 0 };
const SIZE = { x: 40, y: 9.6, z: 4.7 };
const LONG_HOUSE = {
  entities: [
    {
      entity_id: "long_bounds",
      kind: "GREENHOUSE_BOUNDS",
      transform: { position: BASE },
      shape: { shape: "box", size_x: SIZE.x, size_y: SIZE.y, size_z: SIZE.z },
    },
  ],
} as unknown as SceneSnapshot;

// The pose the view is drawn from, as the builder gives it; no WebGL is asked for.
const drawn = vi.hoisted(() => ({ pose: null as CameraPose | null }));
vi.mock("../Viewport", () => ({
  Viewport: ({ initialPose }: { initialPose: CameraPose | null }) => {
    drawn.pose = initialPose;
    return null;
  },
}));
vi.mock("./api", async (original) => ({
  ...(await original<typeof import("./api")>()),
  preview: async () => ({ ok: true, value: LONG_HOUSE }),
}));

const { Builder } = await import("./Builder");

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

describe("the builder's view of the house", () => {
  let shown: Rendered | undefined;
  afterEach(() => {
    shown?.unmount();
    vi.unstubAllGlobals();
  });

  it("frames a 40 m house whole, every corner in view", async () => {
    vi.stubGlobal("fetch", async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.startsWith("/api/builder/basic") || url.startsWith("/api/builder/assess")) {
        return new Response(JSON.stringify(STARTING_HOUSE));
      }
      return new Response(JSON.stringify([]));
    });
    shown = render(<Builder />);
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    click(button(shown.container, "Draft this house"));
    await vi.waitFor(() => expect(drawn.pose).not.toBeNull());

    // The view has no size in a DOM that lays nothing out: the window's shape.
    const aspect = window.innerWidth / window.innerHeight;
    const pose = drawn.pose as CameraPose;
    for (const dx of [-1, 1]) {
      for (const dy of [-1, 1]) {
        for (const z of [0, SIZE.z]) {
          const corner = { x: BASE.x + (dx * SIZE.x) / 2, y: BASE.y + (dy * SIZE.y) / 2, z };
          const { x, y } = onTheView(pose, aspect, corner);
          expect(Math.abs(x)).toBeLessThanOrEqual(1);
          expect(Math.abs(y)).toBeLessThanOrEqual(1);
        }
      }
    }
  });
});
