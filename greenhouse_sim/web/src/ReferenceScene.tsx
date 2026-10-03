import { Canvas } from "@react-three/fiber";

import { WORLD_TO_VIEWER_ROTATION } from "./world";

// A 20 m ground grid with 1 m cells, 2 m world axes, and a 1 m cube resting on
// the grid cell from (1, 1) to (2, 2) m, clear of the axes, so scale and
// orientation read at a glance.
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

// Looking at the origin from above the first quadrant, in Three.js's axes.
const CAMERA = { x: 5, y: 4, z: 6 };
const CAMERA_FIELD_OF_VIEW_DEG = 50;
const AMBIENT_LIGHT_INTENSITY = 0.6;
const SUN_INTENSITY = 1.2;
const SUN = { x: 5, y: 10, z: 7 };

export function ReferenceScene() {
  return (
    <Canvas
      camera={{ position: [CAMERA.x, CAMERA.y, CAMERA.z], fov: CAMERA_FIELD_OF_VIEW_DEG }}
      aria-label="3D view"
    >
      <color attach="background" args={[BACKGROUND_COLOR]} />
      <ambientLight intensity={AMBIENT_LIGHT_INTENSITY} />
      <directionalLight position={[SUN.x, SUN.y, SUN.z]} intensity={SUN_INTENSITY} />
      {/* Three.js's grid lies in its own x-z plane, which is the world's ground. */}
      <gridHelper args={[GRID_SIZE_M, GRID_DIVISIONS, GRID_COLORS.centre, GRID_COLORS.cells]} />
      <group rotation={WORLD_TO_VIEWER_ROTATION}>
        <axesHelper args={[AXES_LENGTH_M]} />
        <mesh position={CUBE_CENTRE}>
          <boxGeometry args={[CUBE_SIZE_M, CUBE_SIZE_M, CUBE_SIZE_M]} />
          <meshStandardMaterial color={CUBE_COLOR} />
        </mesh>
      </group>
    </Canvas>
  );
}
