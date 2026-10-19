import { type Camera, Mesh, type Object3D, type Plane, Raycaster, Vector2, Vector3 } from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

import { CAMERA_CLOSEST_M, CAMERA_NEAR_M } from "./camera";
import { isSeeThrough } from "./selection";

/** The 3D view's controls, and how to let them go. */
export interface ViewControls {
  orbit: OrbitControls;
  dispose: () => void;
}

/** What the wheel zooms towards: what `scene` draws, where the renderer's
 * `clipping` planes, a section's, leave it drawn. */
export interface ZoomTowards {
  scene: () => Object3D | null;
  clipping: () => readonly Plane[];
}

const NOTHING: ZoomTowards = { scene: () => null, clipping: () => [] };

// A notch within this long of the one before it, in milliseconds, is part of
// the same turn of the wheel and keeps its aim. After a pause the scene may
// have changed under the pointer, as a live run's does, so the wheel aims
// again.
const AIM_KEPT_MS = 250;

/** The point the wheel last aimed at, in the viewer's axes, or null over the
 * sky, and where the pointer stood when, and when its turn's latest notch
 * came. */
interface Aim {
  clientX: number;
  clientY: number;
  atMs: number;
  point: Vector3 | null;
}

/**
 * The 3D view's mouse controls of `camera`, listening on `element`: drag to
 * orbit, right-drag to pan and scroll to zoom, never nearer to the point they
 * orbit than the camera's closest approach. Over what `zoomTowards` draws, the
 * wheel zooms towards the point under the pointer, which stays under it; over
 * the sky, towards the point orbited, as before.
 */
export function orbitControls(
  camera: Camera,
  element: HTMLElement,
  zoomTowards: ZoomTowards = NOTHING,
): ViewControls {
  const orbit = new OrbitControls(camera);
  orbit.minDistance = CAMERA_CLOSEST_M;
  const raycaster = new Raycaster();
  // Kept through a turn of the wheel while the pointer stays where it was and
  // only the wheel moves the camera, along the ray through the pointer, so
  // that the point stays under it: a scene of thousands of plants is not
  // searched again at every notch.
  let aimed: Aim | null = null;
  let zooming = false;

  function aim(event: WheelEvent): void {
    // The controls take no notch turned in the middle of a drag, and zoom by
    // none that only scrolls sideways.
    if (event.buttons !== 0 || event.deltaY === 0) {
      return;
    }
    if (
      aimed === null ||
      aimed.clientX !== event.clientX ||
      aimed.clientY !== event.clientY ||
      event.timeStamp - aimed.atMs > AIM_KEPT_MS
    ) {
      const scene = zoomTowards.scene();
      aimed = {
        clientX: event.clientX,
        clientY: event.clientY,
        atMs: event.timeStamp,
        point:
          scene === null
            ? null
            : pointUnder(raycaster, camera, element, event, scene, zoomTowards.clipping()),
      };
    }
    aimed.atMs = event.timeStamp;
    zooming = true;
    orbit.zoomToCursor = aimed.point !== null;
    if (aimed.point !== null) {
      orbitAtTheDepthOf(orbit, aimed.point);
    }
  }
  // Heard before the controls' own listener, which they add as they connect,
  // so that the notch they take is aimed by then.
  element.addEventListener("wheel", aim);
  orbit.connect(element);
  orbit.addEventListener("change", () => {
    if (!zooming) {
      aimed = null;
    }
  });
  // Only the wheel zooms towards the pointer. A middle-button drag zooms too,
  // and keeps zooming towards the point orbited: OrbitControls would aim it
  // at the wrong place on the screen, taking the pointer's x for its y.
  orbit.addEventListener("end", () => {
    zooming = false;
    orbit.zoomToCursor = false;
  });
  return {
    orbit,
    dispose: () => {
      element.removeEventListener("wheel", aim);
      orbit.dispose();
    },
  };
}

/** Where the ray through the pointer meets what `scene` draws, in the viewer's
 * axes, or null if it meets nothing: as a click picks, anything solid before
 * the glazing in front of it. */
function pointUnder(
  raycaster: Raycaster,
  camera: Camera,
  element: HTMLElement,
  event: WheelEvent,
  scene: Object3D,
  clipping: readonly Plane[],
): Vector3 | null {
  const box = element.getBoundingClientRect();
  if (box.width === 0 || box.height === 0) {
    return null;
  }
  const pointer = new Vector2(
    ((event.clientX - box.left) / box.width) * 2 - 1,
    1 - ((event.clientY - box.top) / box.height) * 2,
  );
  camera.updateMatrixWorld();
  raycaster.setFromCamera(pointer, camera);
  // How far a metre along the ray takes it along the way the camera looks.
  const slant = raycaster.ray.direction.dot(camera.getWorldDirection(new Vector3()));
  const hits = raycaster.intersectObject(scene, true).filter(
    (hit) =>
      // Lines, such as the grid and the axes, are drawn to read the scene by.
      hit.object instanceof Mesh &&
      // What the camera does not draw is not aimed at: what lies nearer than
      // its near plane, which is a depth along the way it looks, such as the
      // ground where a preset at the ground's height stands, and what a
      // section cuts away, which raycasting does not.
      hit.distance * slant >= CAMERA_NEAR_M &&
      clipping.every((plane) => plane.distanceToPoint(hit.point) >= 0),
  );
  const hit = hits.find((candidate) => !isSeeThrough(candidate)) ?? hits[0];
  return hit === undefined ? null : hit.point;
}

/** Moves the point orbited along the way the camera looks, to `point`'s
 * depth, and no nearer than the closest approach. The view does not move, but
 * a notch of the wheel now moves the camera a share of its distance to
 * `point`, not to wherever the point orbited was. */
function orbitAtTheDepthOf(orbit: OrbitControls, point: Vector3): void {
  const camera = orbit.object;
  const ahead = camera.getWorldDirection(new Vector3());
  const depth = Math.max(point.clone().sub(camera.position).dot(ahead), orbit.minDistance);
  orbit.target.copy(camera.position).addScaledVector(ahead, depth);
}
