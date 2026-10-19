import { type Camera, Mesh, type Object3D, Raycaster, Vector2, Vector3 } from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

import { CAMERA_CLOSEST_M, CAMERA_NEAR_M } from "./camera";
import { isSeeThrough } from "./selection";

/** The 3D view's controls, and how to let them go. */
export interface ViewControls {
  orbit: OrbitControls;
  dispose: () => void;
}

/** The point the wheel last aimed at, in the viewer's axes, or null over the
 * sky, and where the pointer stood when it did. */
interface Aim {
  clientX: number;
  clientY: number;
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
  zoomTowards: () => Object3D | null = () => null,
): ViewControls {
  const orbit = new OrbitControls(camera);
  orbit.minDistance = CAMERA_CLOSEST_M;
  const raycaster = new Raycaster();
  // What lies nearer than the near plane is not drawn, so it is not aimed at:
  // from a preset at the ground's height, the ground would meet every ray
  // where the camera stands.
  raycaster.near = CAMERA_NEAR_M;
  // Kept while the pointer stays where it was and only the wheel moves the
  // camera, along the ray through the pointer, so that the point stays under
  // it: a scene of thousands of plants is not searched again at every notch.
  let aimed: Aim | null = null;
  let zooming = false;

  function aim(event: WheelEvent): void {
    // The controls take no notch turned in the middle of a drag.
    if (event.buttons !== 0) {
      return;
    }
    if (aimed === null || aimed.clientX !== event.clientX || aimed.clientY !== event.clientY) {
      const scene = zoomTowards();
      aimed = {
        clientX: event.clientX,
        clientY: event.clientY,
        point: scene === null ? null : pointUnder(raycaster, camera, element, event, scene),
      };
    }
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
  // Lines, such as the grid and the axes, are drawn to read the scene by.
  const hits = raycaster.intersectObject(scene, true).filter((hit) => hit.object instanceof Mesh);
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
