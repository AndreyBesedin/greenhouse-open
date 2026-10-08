import { Canvas, useThree } from "@react-three/fiber";
import { useLayoutEffect } from "react";
import { MathUtils, type PerspectiveCamera } from "three";

import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import { SceneView } from "../scene/SceneView";
import { AMBIENT_LIGHT_INTENSITY, BACKGROUND_COLOR, SUN, SUN_INTENSITY } from "../Viewport";
import { WORLD_TO_VIEWER_ROTATION, worldToViewer } from "../world";
import type { CameraSpec } from "./camera";

// What the camera's picture spans in the panel, in CSS pixels across.
const VIEW_WIDTH_PX = 320;
// What the camera sees, from this near to this far, in metres.
const NEAR_M = 0.05;
const FAR_M = 200;

/** Places the canvas's camera where the scene's camera stands, looking at
 * its target, its picture upright, and gives it the projection its
 * intrinsics say: the simulator's pinhole, exactly. */
function SensorCamera({ spec }: { spec: CameraSpec }) {
  const camera = useThree((state) => state.camera) as PerspectiveCamera & { manual?: boolean };
  useLayoutEffect(() => {
    // Its projection is its own; the canvas must not reset it on resize.
    camera.manual = true;
    const eye = worldToViewer(spec.eye);
    const target = worldToViewer(spec.target);
    camera.position.set(eye.x, eye.y, eye.z);
    // The world's up is the viewer's y.
    camera.up.set(0, 1, 0);
    camera.lookAt(target.x, target.y, target.z);
    camera.near = NEAR_M;
    camera.far = FAR_M;
    camera.projectionMatrix.makePerspective(
      (-spec.ppx * NEAR_M) / spec.fx,
      ((spec.width - spec.ppx) * NEAR_M) / spec.fx,
      (spec.ppy * NEAR_M) / spec.fy,
      (-(spec.height - spec.ppy) * NEAR_M) / spec.fy,
      NEAR_M,
      FAR_M,
    );
    camera.projectionMatrixInverse.copy(camera.projectionMatrix).invert();
    camera.updateMatrixWorld();
  }, [camera, spec]);
  return null;
}

/** The camera's field of view across its picture, in degrees. */
export function fieldAcross(spec: CameraSpec): number {
  return MathUtils.radToDeg(2 * Math.atan(spec.width / (2 * spec.fx)));
}

/**
 * What a scene's camera sees: the scene drawn from where it stands, with its
 * intrinsics, as its picture. Its drawing is kept, so that a test can read
 * its pixels.
 */
export function CameraView({ snapshot, spec }: { snapshot: SceneSnapshot; spec: CameraSpec }) {
  const height = (VIEW_WIDTH_PX * spec.height) / spec.width;
  return (
    <section className="camera-panel" aria-label="Camera">
      <p data-testid="camera-intrinsics">
        {spec.cameraId}: {spec.width} × {spec.height} px, {Math.round(fieldAcross(spec))}° across
      </p>
      <div style={{ width: VIEW_WIDTH_PX, height }}>
        <Canvas
          gl={{ preserveDrawingBuffer: true }}
          aria-label="Camera view"
          data-testid="camera-view"
        >
          <SensorCamera spec={spec} />
          <color attach="background" args={[BACKGROUND_COLOR]} />
          <ambientLight intensity={AMBIENT_LIGHT_INTENSITY} />
          <directionalLight position={[SUN.x, SUN.y, SUN.z]} intensity={SUN_INTENSITY} />
          <group rotation={WORLD_TO_VIEWER_ROTATION}>
            <SceneView snapshot={snapshot} />
          </group>
        </Canvas>
      </div>
    </section>
  );
}
