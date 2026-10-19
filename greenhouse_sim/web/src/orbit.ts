import type { Camera } from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

import { CAMERA_CLOSEST_M } from "./camera";

/** The 3D view's mouse controls of `camera`, listening on `element`: drag to
 * orbit, right-drag to pan and scroll to zoom, never nearer to the point they
 * orbit than the camera's closest approach. */
export function orbitControls(camera: Camera, element: HTMLElement): OrbitControls {
  const controls = new OrbitControls(camera, element);
  controls.minDistance = CAMERA_CLOSEST_M;
  return controls;
}
