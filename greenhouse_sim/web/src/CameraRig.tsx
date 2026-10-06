import { useThree } from "@react-three/fiber";
import { useEffect, useRef } from "react";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

import { CAMERA_PRESETS, type CameraPose, DEFAULT_PRESET, type PresetRequest } from "./camera";
import { worldToViewer } from "./world";

/** Orbit, pan and zoom with the mouse, starting from the default preset or a
 * given pose, and moving to any preset that is requested. */
export function CameraRig({
  request,
  initialPose = null,
}: {
  request: PresetRequest | null;
  initialPose?: CameraPose | null;
}) {
  const camera = useThree((state) => state.camera);
  const domElement = useThree((state) => state.gl.domElement);
  const controls = useRef<OrbitControls | null>(null);

  useEffect(() => {
    const orbit = new OrbitControls(camera, domElement);
    controls.current = orbit;
    moveTo(orbit, initialPose ?? CAMERA_PRESETS[DEFAULT_PRESET]);
    return () => {
      orbit.dispose();
      controls.current = null;
    };
  }, [camera, domElement, initialPose]);

  useEffect(() => {
    if (request !== null && controls.current !== null) {
      moveTo(controls.current, CAMERA_PRESETS[request.preset]);
    }
  }, [request]);

  return null;
}

function moveTo(controls: OrbitControls, pose: CameraPose): void {
  const position = worldToViewer(pose.position);
  const target = worldToViewer(pose.target);
  controls.object.position.set(position.x, position.y, position.z);
  controls.target.set(target.x, target.y, target.z);
  controls.update();
}
