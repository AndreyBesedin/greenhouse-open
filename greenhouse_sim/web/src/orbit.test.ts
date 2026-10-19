// @vitest-environment jsdom
import { PerspectiveCamera } from "three";
import { afterEach, describe, expect, it } from "vitest";

import {
  CAMERA_CLOSEST_M,
  CAMERA_FIELD_OF_VIEW_DEG,
  CAMERA_NEAR_M,
  CAMERA_PRESETS,
  type CameraPose,
} from "./camera";
import { orbitControls } from "./orbit";
import { worldToViewer } from "./world";

// A mouse wheel's notch, as Chromium reports it.
const NOTCH_PX = 100;
// A part of a long greenhouse no preset frames, as the address can place the
// camera to look at it (`&camera=26:6:8,23.3:6:1`): far enough from the
// origin that a position within a hair of it rounds coarsely.
const FAR_FROM_THE_ORIGIN: CameraPose = {
  position: { x: 26, y: 6, z: 8 },
  target: { x: 23.3, y: 6, z: 1 },
};

let disposers: (() => void)[] = [];
afterEach(() => {
  for (const dispose of disposers) {
    dispose();
  }
  disposers = [];
});

/** The view's controls, looking from a pose, and the distance from the
 * camera to the point they orbit. */
function controlsAt(pose: CameraPose) {
  const camera = new PerspectiveCamera(CAMERA_FIELD_OF_VIEW_DEG, 1, CAMERA_NEAR_M);
  const element = document.createElement("div");
  const controls = orbitControls(camera, element);
  disposers.push(() => controls.dispose());
  const position = worldToViewer(pose.position);
  const target = worldToViewer(pose.target);
  camera.position.set(position.x, position.y, position.z);
  controls.target.set(target.x, target.y, target.z);
  controls.update();
  return {
    element,
    distance: () => camera.position.distanceTo(controls.target),
  };
}

/** Turns the wheel by `notches`: in, towards the point orbited, while
 * negative, as a wheel turned away from the user scrolls up the page. */
function turnWheel(element: HTMLElement, notches: number): void {
  for (let notch = 0; notch < Math.abs(notches); notch += 1) {
    element.dispatchEvent(
      new WheelEvent("wheel", { deltaY: Math.sign(notches) * NOTCH_PX, cancelable: true }),
    );
  }
}

describe("the view's orbit controls", () => {
  it("stop zooming in at the camera's closest approach, beyond its near plane", () => {
    const { element, distance } = controlsAt(CAMERA_PRESETS.isometric);

    turnWheel(element, -300);

    expect(distance()).toBeCloseTo(CAMERA_CLOSEST_M);
    expect(CAMERA_CLOSEST_M).toBeGreaterThan(CAMERA_NEAR_M);
  });

  it("back out on the first notches of the wheel after a zoom in far past it", () => {
    const { element, distance } = controlsAt(CAMERA_PRESETS.isometric);
    turnWheel(element, -300);

    turnWheel(element, 20);

    // Each notch out moves the camera a twentieth further away again.
    expect(distance()).toBeGreaterThan(2 * CAMERA_CLOSEST_M);
  });

  it("are never pinned to a point far from the origin, however long the wheel turns in", () => {
    const { element, distance } = controlsAt(FAR_FROM_THE_ORIGIN);
    turnWheel(element, -1000);

    turnWheel(element, 100);

    expect(distance()).toBeGreaterThan(1);
  });
});
