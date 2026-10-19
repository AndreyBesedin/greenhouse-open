import { useThree } from "@react-three/fiber";
import { type RefObject, useEffect, useRef } from "react";
import type { Object3D } from "three";
import type { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

import { CAMERA_PRESETS, type CameraPose, DEFAULT_PRESET, type PresetRequest } from "./camera";
import { orbitControls } from "./orbit";
import { worldToViewer } from "./world";

/** Orbit, pan and zoom with the mouse, starting from the default preset or a
 * given pose, and moving to any preset that is requested; each move asks for
 * a frame, so that a view drawn only on demand follows it. */
export function CameraRig({
  request,
  initialPose = null,
  zoomTowards = null,
}: {
  request: PresetRequest | null;
  initialPose?: CameraPose | null;
  /** What the wheel zooms towards, where the pointer is over it. */
  zoomTowards?: RefObject<Object3D | null> | null;
}) {
  const camera = useThree((state) => state.camera);
  const gl = useThree((state) => state.gl);
  const invalidate = useThree((state) => state.invalidate);
  const controls = useRef<OrbitControls | null>(null);

  useEffect(() => {
    const view = orbitControls(camera, gl.domElement, {
      scene: () => zoomTowards?.current ?? null,
      // The planes a section cuts the view by, if any.
      clipping: () => gl.clippingPlanes,
    });
    const orbit = view.orbit;
    const redraw = () => invalidate();
    orbit.addEventListener("change", redraw);
    controls.current = orbit;
    moveTo(orbit, initialPose ?? CAMERA_PRESETS[DEFAULT_PRESET]);
    invalidate();
    return () => {
      orbit.removeEventListener("change", redraw);
      view.dispose();
      controls.current = null;
    };
  }, [camera, gl, initialPose, invalidate, zoomTowards]);

  useEffect(() => {
    if (request !== null && controls.current !== null) {
      moveTo(controls.current, CAMERA_PRESETS[request.preset]);
      invalidate();
    }
  }, [request, invalidate]);

  return null;
}

function moveTo(controls: OrbitControls, pose: CameraPose): void {
  const position = worldToViewer(pose.position);
  const target = worldToViewer(pose.target);
  controls.object.position.set(position.x, position.y, position.z);
  controls.target.set(target.x, target.y, target.z);
  controls.update();
}
