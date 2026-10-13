import { useThree } from "@react-three/fiber";
import { useEffect, useRef } from "react";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

import { CAMERA_PRESETS, type CameraPose, DEFAULT_PRESET, type PresetRequest } from "./camera";
import { worldToViewer } from "./world";

/** Orbit, pan and zoom with the mouse, starting from the default preset or a
 * given pose, and moving to any preset that is requested; each move asks for
 * a frame, so that a view drawn only on demand follows it. */
export function CameraRig({
  request,
  initialPose = null,
}: {
  request: PresetRequest | null;
  initialPose?: CameraPose | null;
}) {
  const camera = useThree((state) => state.camera);
  const domElement = useThree((state) => state.gl.domElement);
  const invalidate = useThree((state) => state.invalidate);
  const controls = useRef<OrbitControls | null>(null);

  useEffect(() => {
    const orbit = new OrbitControls(camera, domElement);
    const redraw = () => invalidate();
    orbit.addEventListener("change", redraw);
    controls.current = orbit;
    moveTo(orbit, initialPose ?? CAMERA_PRESETS[DEFAULT_PRESET]);
    invalidate();
    return () => {
      orbit.removeEventListener("change", redraw);
      orbit.dispose();
      controls.current = null;
    };
  }, [camera, domElement, initialPose, invalidate]);

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
