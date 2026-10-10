import { Canvas, type ThreeEvent } from "@react-three/fiber";
import { type ReactNode, useRef } from "react";
import { type Group, PCFShadowMap } from "three";
import { CameraRig } from "./CameraRig";
import { CAMERA_FIELD_OF_VIEW_DEG, type CameraPose, type PresetRequest } from "./camera";
import { Overlays } from "./debug/DebugPrimitives";
import type { OverlayPrimitive } from "./debug/overlays";
import type { Colouring } from "./debug/scalar";
import { HudProbe } from "./HudProbe";
import type { ViewSample } from "./readouts";
import { Section, type SectionPlane } from "./Section";
import type { SceneSnapshot } from "./scene/generated/snapshotTypes";
import { SceneView } from "./scene/SceneView";
import { SunLight } from "./scene/SunLight";
import { CLICK_TOLERANCE_PX, pickEntity } from "./selection";
import type { SunLightPose } from "./weather/sunlight";
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
export const BACKGROUND_COLOR = "#f4f4f2";

export const AMBIENT_LIGHT_INTENSITY = 0.6;
// Under the sun the sky's ambient light is dimmer, so that what the sun
// lights stands out from what lies in shade.
export const SUNLIT_AMBIENT_INTENSITY = 0.35;
export const SUN_INTENSITY = 1.2;
export const SUN = { x: 5, y: 10, z: 7 };
// The sun's shadows: filtered, and drawn only when they change
// (`scene/SunLight`).
const SUN_SHADOWS = { enabled: true, type: PCFShadowMap, autoUpdate: false };
// How near a click must pass to a line, such as the world axes, to land on
// it. Three.js's default of a metre would let the axes take clicks meant for
// the ground around them.
const LINE_PICK_TOLERANCE_M = 0.05;
// The undrawn ground plane that reports where the pointer meets the ground,
// by name, and how far it reaches: well past the drawn grid, so that a
// probe can be placed anywhere in a long greenhouse.
const GROUND = "ground";
const GROUND_SIZE_M = 200;

export function Viewport({
  snapshot,
  presetRequest,
  selectedId = null,
  colouring = null,
  overlays = [],
  showBounds = false,
  byCategory = false,
  initialPose = null,
  section = null,
  sunlight = null,
  onSample,
  onPointer,
  onSelect,
  onProbe = null,
  children = null,
}: {
  snapshot: SceneSnapshot | null;
  presetRequest: PresetRequest | null;
  selectedId?: string | null;
  colouring?: Colouring | null;
  overlays?: readonly OverlayPrimitive[];
  showBounds?: boolean;
  byCategory?: boolean;
  /** Where the camera starts, rather than the default preset. */
  initialPose?: CameraPose | null;
  /** Cuts the view by a plane, keeping what lies behind it. */
  section?: SectionPlane | null;
  /** Lights the scene from the sun, casting shadows, while it is up; by the
   * sky's ambient light alone at night; by the fixed light (null) otherwise. */
  sunlight?: SunLightPose | "night" | null;
  onSample: (sample: ViewSample) => void;
  onPointer: (point: Point3 | null) => void;
  /** A click picked an entity, or nothing (null). Drags orbit and pick nothing. */
  onSelect: (entityId: string | null) => void;
  /** While set, a click picks the point on the ground under it instead, to
   * place a probe there. */
  onProbe?: ((ground: Point3) => void) | null;
  /** More to draw in the world's frame, such as an environment field, which
   * clicks pass through. */
  children?: ReactNode;
}) {
  const casters = useRef<Group>(null);

  function pick(event: ThreeEvent<MouseEvent>): void {
    // Every hit along the ray reaches this group; the nearest entity decides.
    event.stopPropagation();
    if (event.delta > CLICK_TOLERANCE_PX) {
      return;
    }
    if (onProbe !== null) {
      const ground = event.intersections.find((hit) => hit.object.name === GROUND);
      if (ground !== undefined) {
        onProbe(viewerToWorld(ground.point));
      }
      return;
    }
    onSelect(pickEntity(event.intersections));
  }

  return (
    <Canvas
      camera={{ fov: CAMERA_FIELD_OF_VIEW_DEG }}
      data-testid="main-view"
      data-light={sunlight === null ? "fixed" : sunlight === "night" ? "night" : "sun"}
      shadows={sunlight !== null && sunlight !== "night" ? SUN_SHADOWS : false}
      onCreated={({ raycaster }) => {
        raycaster.params.Line = { threshold: LINE_PICK_TOLERANCE_M };
      }}
      onPointerMissed={() => {
        if (onProbe === null) {
          onSelect(null);
        }
      }}
      aria-label="3D view"
    >
      <CameraRig request={presetRequest} initialPose={initialPose} />
      <Section plane={section} />
      <HudProbe onSample={onSample} />
      <color attach="background" args={[BACKGROUND_COLOR]} />
      <ambientLight
        intensity={
          sunlight === null || sunlight === "night"
            ? AMBIENT_LIGHT_INTENSITY
            : SUNLIT_AMBIENT_INTENSITY
        }
      />
      {sunlight === null ? (
        <directionalLight position={[SUN.x, SUN.y, SUN.z]} intensity={SUN_INTENSITY} />
      ) : (
        sunlight !== "night" && <SunLight pose={sunlight} casters={casters} />
      )}
      {/* Three.js's grid lies in its own x-z plane, which is the world's ground. */}
      <gridHelper args={[GRID_SIZE_M, GRID_DIVISIONS, GRID_COLORS.centre, GRID_COLORS.cells]} />
      <group rotation={WORLD_TO_VIEWER_ROTATION}>
        {/* biome-ignore lint/a11y/noStaticElementInteractions: a Three.js group in the canvas, not a page element. */}
        <group onClick={pick} ref={casters}>
          {snapshot === null ? (
            <>
              <axesHelper args={[AXES_LENGTH_M]} />
              <mesh position={CUBE_CENTRE}>
                <boxGeometry args={[CUBE_SIZE_M, CUBE_SIZE_M, CUBE_SIZE_M]} />
                <meshStandardMaterial color={CUBE_COLOR} />
              </mesh>
            </>
          ) : (
            <SceneView
              snapshot={snapshot}
              selectedId={selectedId}
              colouring={colouring}
              showBounds={showBounds}
              byCategory={byCategory}
            />
          )}
          {/* An undrawn ground plane that reports where the pointer meets the ground. */}
          <mesh
            name={GROUND}
            onPointerMove={(event) => onPointer(viewerToWorld(event.point))}
            onPointerOut={() => onPointer(null)}
          >
            <planeGeometry args={[GROUND_SIZE_M, GROUND_SIZE_M]} />
            <meshBasicMaterial visible={false} />
          </mesh>
        </group>
        <Overlays primitives={overlays} />
        {children}
      </group>
    </Canvas>
  );
}
