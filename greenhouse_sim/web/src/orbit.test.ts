// @vitest-environment jsdom
import {
  Group,
  Mesh,
  MeshBasicMaterial,
  type Object3D,
  PerspectiveCamera,
  Plane,
  PlaneGeometry,
  Raycaster,
  Vector2,
  Vector3,
} from "three";
import { afterEach, describe, expect, it, vi } from "vitest";

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
// The view's size on the page, in pixels.
const VIEW = { width: 200, height: 100 };
// Right of and below the middle of the view, where the isometric view looks
// at the ground in front of the origin.
const OFF_THE_MIDDLE = { x: 150, y: 70 };
const GROUND_SIZE_M = 200;

let disposers: (() => void)[] = [];
afterEach(() => {
  for (const dispose of disposers) {
    dispose();
  }
  disposers = [];
});

/** The ground, as the viewer's scene lays it, in the viewer's axes: y up. */
function ground(): Mesh {
  const plane = new Mesh(new PlaneGeometry(GROUND_SIZE_M, GROUND_SIZE_M), new MeshBasicMaterial());
  plane.rotation.x = -Math.PI / 2;
  plane.updateMatrixWorld();
  return plane;
}

/** A pane of glazing across the view, `ahead` metres in front of a pose's
 * camera, as the scene marks its walls and roofs. */
function glazingBefore(pose: CameraPose, ahead: number): Mesh {
  const camera = poseCamera(pose);
  const pane = new Mesh(new PlaneGeometry(GROUND_SIZE_M, GROUND_SIZE_M), new MeshBasicMaterial());
  pane.position
    .copy(camera.position)
    .addScaledVector(camera.getWorldDirection(new Vector3()), ahead);
  pane.quaternion.copy(camera.quaternion);
  pane.userData.seeThrough = true;
  pane.updateMatrixWorld();
  return pane;
}

function poseCamera(pose: CameraPose): PerspectiveCamera {
  const camera = new PerspectiveCamera(
    CAMERA_FIELD_OF_VIEW_DEG,
    VIEW.width / VIEW.height,
    CAMERA_NEAR_M,
  );
  const position = worldToViewer(pose.position);
  const target = worldToViewer(pose.target);
  camera.position.set(position.x, position.y, position.z);
  camera.lookAt(target.x, target.y, target.z);
  camera.updateMatrixWorld();
  return camera;
}

/** The view's controls, looking from a pose over a scene, if any, on a view
 * of `VIEW`'s size. */
function controlsAt(
  pose: CameraPose,
  scene: Object3D | null = null,
  clipping: readonly Plane[] = [],
) {
  const camera = poseCamera(pose);
  const element = document.createElement("div");
  element.getBoundingClientRect = () => new DOMRect(0, 0, VIEW.width, VIEW.height);
  const { orbit, dispose } = orbitControls(camera, element, {
    scene: () => scene,
    clipping: () => clipping,
  });
  disposers.push(dispose);
  const target = worldToViewer(pose.target);
  orbit.target.set(target.x, target.y, target.z);
  orbit.update();
  return {
    camera,
    orbit,
    element,
    distance: () => camera.position.distanceTo(orbit.target),
  };
}

/** Turns the wheel by `notches` with the pointer at `at`, in the view's
 * pixels, `laterMs` after now: in, towards the point orbited, while negative,
 * as a wheel turned away from the user scrolls up the page. */
function turnWheel(element: HTMLElement, notches: number, at = { x: 0, y: 0 }, laterMs = 0) {
  for (let notch = 0; notch < Math.abs(notches); notch += 1) {
    const event = new WheelEvent("wheel", {
      deltaY: Math.sign(notches) * NOTCH_PX,
      clientX: at.x,
      clientY: at.y,
      cancelable: true,
    });
    Object.defineProperty(event, "timeStamp", { value: event.timeStamp + laterMs });
    element.dispatchEvent(event);
  }
}

/** Where the ray through a pixel of the view first meets `scene`. */
function pointAt(camera: PerspectiveCamera, scene: Object3D, at: { x: number; y: number }) {
  const raycaster = new Raycaster();
  raycaster.setFromCamera(
    new Vector2((at.x / VIEW.width) * 2 - 1, 1 - (at.y / VIEW.height) * 2),
    camera,
  );
  const hit = raycaster.intersectObject(scene, true)[0];
  if (hit === undefined) {
    throw new Error("nothing under the pixel");
  }
  return hit.point;
}

/** The pixel of the view a point is drawn at. */
function pixelOf(camera: PerspectiveCamera, point: Vector3): { x: number; y: number } {
  camera.updateMatrixWorld();
  const drawn = point.clone().project(camera);
  return { x: ((drawn.x + 1) / 2) * VIEW.width, y: ((1 - drawn.y) / 2) * VIEW.height };
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

describe("the wheel, over the scene", () => {
  it("zooms towards the point under the pointer, which stays under it", () => {
    const scene = ground();
    const { camera, element } = controlsAt(CAMERA_PRESETS.isometric, scene);
    const point = pointAt(camera, scene, OFF_THE_MIDDLE);
    const before = camera.position.distanceTo(point);
    const looking = camera.getWorldDirection(new Vector3());

    turnWheel(element, -20, OFF_THE_MIDDLE);

    const drawn = pixelOf(camera, point);
    expect(drawn.x).toBeCloseTo(OFF_THE_MIDDLE.x);
    expect(drawn.y).toBeCloseTo(OFF_THE_MIDDLE.y);
    expect(camera.position.distanceTo(point)).toBeLessThan(0.5 * before);
    // Without turning: the view moves towards the point, it does not jump to it.
    expect(camera.getWorldDirection(new Vector3()).angleTo(looking)).toBeCloseTo(0);
  });

  it("then orbits a point on the way the camera looks, a notch nearer than the point was", () => {
    const scene = ground();
    const { camera, orbit, element } = controlsAt(CAMERA_PRESETS.isometric, scene);
    const ahead = camera.getWorldDirection(new Vector3());
    const depth = pointAt(camera, scene, OFF_THE_MIDDLE).sub(camera.position).dot(ahead);

    turnWheel(element, -1, OFF_THE_MIDDLE);

    const toTarget = orbit.target.clone().sub(camera.position);
    expect(toTarget.angleTo(ahead)).toBeCloseTo(0);
    expect(toTarget.length()).toBeCloseTo(0.95 * depth);
  });

  it("stops at the closest approach to the point, and backs away from it again", () => {
    const scene = ground();
    const { camera, element } = controlsAt(CAMERA_PRESETS.isometric, scene);
    const point = pointAt(camera, scene, OFF_THE_MIDDLE);

    turnWheel(element, -300, OFF_THE_MIDDLE);
    const closest = camera.position.distanceTo(point);
    turnWheel(element, 20, OFF_THE_MIDDLE);

    expect(closest).toBeGreaterThan(CAMERA_CLOSEST_M);
    expect(closest).toBeLessThan(2 * CAMERA_CLOSEST_M);
    expect(camera.position.distanceTo(point)).toBeGreaterThan(2 * closest);
    expect(pixelOf(camera, point).x).toBeCloseTo(OFF_THE_MIDDLE.x);
  });

  it("zooms through glazing towards what is solid behind it", () => {
    const pose = CAMERA_PRESETS.isometric;
    const behind = ground();
    const scene = new Group().add(glazingBefore(pose, 2), behind);
    const { camera, element } = controlsAt(pose, scene);
    const point = pointAt(camera, behind, OFF_THE_MIDDLE);
    const before = camera.position.distanceTo(point);

    turnWheel(element, -40, OFF_THE_MIDDLE);

    // Past the pane, two metres ahead, and on towards the ground.
    expect(camera.position.distanceTo(point)).toBeLessThan(0.3 * before);
    expect(pixelOf(camera, point).y).toBeCloseTo(OFF_THE_MIDDLE.y);
  });

  it("aims past what is nearer than the near plane, along the way the camera looks", () => {
    // Facing the front view's camera: a solid pane 9 cm ahead, not drawn, and
    // a wall 5 m ahead. Near the side of the view the ray meets the pane more
    // than the near plane's 10 cm away.
    const near = new Mesh(new PlaneGeometry(GROUND_SIZE_M, GROUND_SIZE_M), new MeshBasicMaterial());
    near.position.z = worldToViewer(CAMERA_PRESETS.front.position).z - 0.09;
    const wall = new Mesh(new PlaneGeometry(GROUND_SIZE_M, GROUND_SIZE_M), new MeshBasicMaterial());
    wall.position.z = worldToViewer(CAMERA_PRESETS.front.position).z - 5;
    const scene = new Group().add(near, wall);
    scene.updateMatrixWorld(true);
    const { camera, element } = controlsAt(CAMERA_PRESETS.front, scene);
    const from = camera.position.clone();

    turnWheel(element, -10, { x: VIEW.width * 0.95, y: VIEW.height / 2 });

    // Towards the wall: aimed at the pane, the camera would stand still at its
    // closest approach to it.
    expect(camera.position.distanceTo(from)).toBeGreaterThan(1);
  });

  it("aims past what a section cuts away", () => {
    const roof = ground();
    roof.position.y = 3;
    roof.updateMatrixWorld();
    const behind = ground();
    // Keeps what lies below 2.5 m.
    const section = new Plane(new Vector3(0, -1, 0), 2.5);
    const { camera, element } = controlsAt(
      CAMERA_PRESETS.isometric,
      new Group().add(roof, behind),
      [section],
    );
    const point = pointAt(camera, behind, OFF_THE_MIDDLE);
    const before = camera.position.distanceTo(point);

    turnWheel(element, -20, OFF_THE_MIDDLE);

    expect(camera.position.distanceTo(point)).toBeLessThan(0.5 * before);
  });

  it("moves nothing for a sideways scroll, which does not zoom", () => {
    const { orbit, element } = controlsAt(CAMERA_PRESETS.isometric, ground());

    element.dispatchEvent(
      new WheelEvent("wheel", {
        deltaX: NOTCH_PX,
        clientX: OFF_THE_MIDDLE.x,
        clientY: OFF_THE_MIDDLE.y,
      }),
    );

    expect(orbit.target.length()).toBeCloseTo(0);
  });

  it("searches the scene once while the pointer stays put, and again once the view turns", () => {
    const scene = ground();
    const searched = vi.spyOn(scene, "raycast");
    const { orbit, element } = controlsAt(CAMERA_PRESETS.isometric, scene);

    turnWheel(element, -10, OFF_THE_MIDDLE);
    expect(searched).toHaveBeenCalledTimes(1);

    turnWheel(element, -1, { x: OFF_THE_MIDDLE.x + 1, y: OFF_THE_MIDDLE.y });
    expect(searched).toHaveBeenCalledTimes(2);

    orbit.rotateLeft(0.1);
    turnWheel(element, -1, { x: OFF_THE_MIDDLE.x + 1, y: OFF_THE_MIDDLE.y });
    expect(searched).toHaveBeenCalledTimes(3);
  });

  it("searches it again after a pause, for the scene may have changed under the pointer", () => {
    const scene = ground();
    const searched = vi.spyOn(scene, "raycast");
    const { element } = controlsAt(CAMERA_PRESETS.isometric, scene);

    turnWheel(element, -1, OFF_THE_MIDDLE);
    turnWheel(element, -1, OFF_THE_MIDDLE, 1000);

    expect(searched).toHaveBeenCalledTimes(2);
  });
});

describe("the wheel, with nothing under the pointer", () => {
  // The front view stands on the ground, looking along it.
  const FRONT = worldToViewer(CAMERA_PRESETS.front.position);

  it.each([
    ["over the sky, above the middle of the view", { x: VIEW.width / 4, y: VIEW.height / 10 }],
    // The ground meets the ray there only where the camera stands.
    ["along the ground, at the camera's own height", { x: VIEW.width / 4, y: VIEW.height * 0.9 }],
  ])("zooms towards the point orbited, as before: %s", (_, at) => {
    const { camera, orbit, element } = controlsAt(CAMERA_PRESETS.front, ground());

    turnWheel(element, -10, at);

    expect(camera.position.x).toBeCloseTo(0);
    expect(camera.position.y).toBeCloseTo(0);
    expect(camera.position.z).toBeCloseTo(FRONT.z * 0.95 ** 10);
    expect(orbit.target.length()).toBeCloseTo(0);
  });
});
