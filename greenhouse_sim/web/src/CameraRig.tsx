import { useThree } from "@react-three/fiber";
import { useEffect, useRef } from "react";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

import { CAMERA_PRESETS, DEFAULT_PRESET, type PresetName, type PresetRequest } from "./camera";
import { worldToViewer } from "./world";

/** Orbit, pan and zoom with the mouse, starting from the default preset, and
 * moving to any preset that is requested. */
export function CameraRig({ request }: { request: PresetRequest | null }) {
  const camera = useThree((state) => state.camera);
  const domElement = useThree((state) => state.gl.domElement);
  const controls = useRef<OrbitControls | null>(null);

  useEffect(() => {
    const orbit = new OrbitControls(camera, domElement);
    controls.current = orbit;
    moveTo(orbit, DEFAULT_PRESET);
    return () => {
      orbit.dispose();
      controls.current = null;
    };
  }, [camera, domElement]);

  useEffect(() => {
    if (request !== null && controls.current !== null) {
      moveTo(controls.current, request.preset);
    }
  }, [request]);

  return null;
}

function moveTo(controls: OrbitControls, preset: PresetName): void {
  const pose = CAMERA_PRESETS[preset];
  const position = worldToViewer(pose.position);
  const target = worldToViewer(pose.target);
  controls.object.position.set(position.x, position.y, position.z);
  controls.target.set(target.x, target.y, target.z);
  controls.update();
}
