import { Canvas } from "@react-three/fiber";
import { CameraRig } from "./CameraRig";
import type { PresetRequest } from "./camera";
import { HudProbe } from "./HudProbe";
import type { ViewSample } from "./readouts";
import type { SceneSnapshot } from "./scene/generated/snapshotTypes";
import { SceneView } from "./scene/SceneView";
import { type Point3, viewerToWorld, WORLD_TO_VIEWER_ROTATION } from "./world";

// A 20 m ground grid with 1 m cells is always shown. Without a scene, 2 m world
// axes and a 1 m cube resting on the grid cell from (1, 1) to (2, 2) m, clear
// of the axes, make scale and orientation read at a glance.
const GRID_SIZE_M = 20;
const GRID_DIVISIONS = 20;
const AXES_LENGTH_M = 2;
const CUBE_SIZE_M = 1;
const CUBE_CORNER_M = 1;
const CUBE_CENTRE: [number, number, number] = [
  CUBE_CORNER_M + CUBE_SIZE_M / 2,
  CUBE_CORNER_M + CUBE_SIZE_M / 2,
  CUBE_SIZE_M / 2,
];
const CUBE_COLOR = "#4f8a5b";
const GRID_COLORS = { centre: "#888888", cells: "#cccccc" };
const BACKGROUND_COLOR = "#f4f4f2";

const CAMERA_FIELD_OF_VIEW_DEG = 50;
const AMBIENT_LIGHT_INTENSITY = 0.6;
const SUN_INTENSITY = 1.2;
const SUN = { x: 5, y: 10, z: 7 };

export function Viewport({
  snapshot,
  presetRequest,
  onSample,
  onPointer,
}: {
  snapshot: SceneSnapshot | null;
  presetRequest: PresetRequest | null;
  onSample: (sample: ViewSample) => void;
  onPointer: (point: Point3 | null) => void;
}) {
  return (
    <Canvas camera={{ fov: CAMERA_FIELD_OF_VIEW_DEG }} aria-label="3D view">
      <CameraRig request={presetRequest} />
      <HudProbe onSample={onSample} />
      <color attach="background" args={[BACKGROUND_COLOR]} />
      <ambientLight intensity={AMBIENT_LIGHT_INTENSITY} />
      <directionalLight position={[SUN.x, SUN.y, SUN.z]} intensity={SUN_INTENSITY} />
      {/* Three.js's grid lies in its own x-z plane, which is the world's ground. */}
      <gridHelper args={[GRID_SIZE_M, GRID_DIVISIONS, GRID_COLORS.centre, GRID_COLORS.cells]} />
      <group rotation={WORLD_TO_VIEWER_ROTATION}>
        {snapshot === null ? (
          <>
            <axesHelper args={[AXES_LENGTH_M]} />
            <mesh position={CUBE_CENTRE}>
              <boxGeometry args={[CUBE_SIZE_M, CUBE_SIZE_M, CUBE_SIZE_M]} />
              <meshStandardMaterial color={CUBE_COLOR} />
            </mesh>
          </>
        ) : (
          <SceneView snapshot={snapshot} />
        )}
        {/* An undrawn ground plane that reports where the pointer meets the ground. */}
        <mesh
          onPointerMove={(event) => onPointer(viewerToWorld(event.point))}
          onPointerOut={() => onPointer(null)}
        >
          <planeGeometry args={[GRID_SIZE_M, GRID_SIZE_M]} />
          <meshBasicMaterial visible={false} />
        </mesh>
      </group>
    </Canvas>
  );
}
