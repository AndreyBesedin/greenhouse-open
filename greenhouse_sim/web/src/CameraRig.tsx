import { useFrame, useThree } from "@react-three/fiber";
import { type RefObject, useEffect, useRef } from "react";
import type { Object3D } from "three";
import type { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

import { CAMERA_PRESETS, type CameraPose, DEFAULT_PRESET, type PresetRequest } from "./camera";
import { orbitControls } from "./orbit";
import { worldToViewer } from "./world";

/** Orbit, pan and zoom with the mouse, starting from the default preset or a
 * given pose, and moving to any preset that is requested; each move asks for
 * a frame, so that a view drawn only on demand follows it, and the view draws
 * every frame while a drag holds the controls. */
export function CameraRig({
  request,
  initialPose = null,
  zoomTowards = null,
  still = false,
}: {
  request: PresetRequest | null;
  initialPose?: CameraPose | null;
  /** What the wheel zooms towards, where the pointer is over it. */
  zoomTowards?: RefObject<Object3D | null> | null;
  /** Whether drags leave the camera where it is, to move what is in view
   * (#209): the wheel still zooms. */
  still?: boolean;
}) {
  const camera = useThree((state) => state.camera);
  const gl = useThree((state) => state.gl);
  const invalidate = useThree((state) => state.invalidate);
  const controls = useRef<OrbitControls | null>(null);
  const held = useRef(still);
  held.current = still;
  // Whether a drag holds the controls. Meanwhile the view draws every frame,
  // as it did before it drew on demand (decision 0053): what it draws is
  // moving anyway, and its frame rate is the renderer's, not the pointer's,
  // for the benchmarks, which orbit with the button held (decision 0015).
  const dragged = useRef(false);

  useEffect(() => {
    const view = orbitControls(camera, gl.domElement, {
      scene: () => zoomTowards?.current ?? null,
      // The planes a section cuts the view by, if any.
      clipping: () => gl.clippingPlanes,
    });
    const orbit = view.orbit;
    // The controls turn the camera without updating its world matrix, which
    // a frame would. The view draws only when something changes (decision
    // 0053), so a click can come before that frame, and is picked from the
    // camera as it now stands.
    const redraw = () => {
      camera.updateMatrixWorld();
      invalidate();
    };
    const grab = () => {
      dragged.current = true;
      invalidate();
    };
    const release = () => {
      dragged.current = false;
    };
    orbit.addEventListener("change", redraw);
    orbit.addEventListener("start", grab);
    orbit.addEventListener("end", release);
    controls.current = orbit;
    holdStill(orbit, held.current);
    moveTo(orbit, initialPose ?? CAMERA_PRESETS[DEFAULT_PRESET]);
    invalidate();
    return () => {
      orbit.removeEventListener("change", redraw);
      orbit.removeEventListener("start", grab);
      orbit.removeEventListener("end", release);
      dragged.current = false;
      view.dispose();
      controls.current = null;
    };
  }, [camera, gl, initialPose, invalidate, zoomTowards]);

  useEffect(() => {
    if (controls.current !== null) {
      holdStill(controls.current, still);
    }
  }, [still]);

  useFrame(() => {
    if (dragged.current) {
      invalidate();
    }
  });

  useEffect(() => {
    if (request !== null && controls.current !== null) {
      moveTo(controls.current, CAMERA_PRESETS[request.preset]);
      invalidate();
    }
  }, [request, invalidate]);

  return null;
}

function holdStill(controls: OrbitControls, still: boolean): void {
  controls.enableRotate = !still;
  controls.enablePan = !still;
}

function moveTo(controls: OrbitControls, pose: CameraPose): void {
  const position = worldToViewer(pose.position);
  const target = worldToViewer(pose.target);
  controls.object.position.set(position.x, position.y, position.z);
  controls.target.set(target.x, target.y, target.z);
  controls.update();
}
