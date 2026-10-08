import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { type PointerEvent, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { MathUtils, type PerspectiveCamera } from "three";

import { formatCount, formatMetres } from "../readouts";
import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import { SceneView } from "../scene/SceneView";
import { AMBIENT_LIGHT_INTENSITY, BACKGROUND_COLOR, SUN, SUN_INTENSITY } from "../Viewport";
import { WORLD_TO_VIEWER_ROTATION, worldToViewer } from "../world";
import type { CameraSpec } from "./camera";
import {
  type CameraPasses,
  depthPicture,
  depthRange,
  instanceColor,
  instancePicture,
  passesAt,
} from "./passes";
import { renderPasses } from "./renderPasses";

// What the camera's picture spans in the panel, in CSS pixels across.
const VIEW_WIDTH_PX = 320;
// What the camera sees, from this near to this far, in metres.
const NEAR_M = 0.05;
const FAR_M = 200;
const RGBA = 4;

type Pass = "rgb" | "depth" | "instance";
const PASS_LABELS: Record<Pass, string> = { rgb: "RGB", depth: "Depth", instance: "Instance" };
const PASS_ORDER: readonly Pass[] = ["rgb", "depth", "instance"];

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

/** Draws the camera's depth and instance passes in the first frame that
 * shows its scene, and again in the first after the scene or the camera
 * changes: by then, what they show is in place. */
function PassReader({
  snapshot,
  spec,
  onPasses,
}: {
  snapshot: SceneSnapshot;
  spec: CameraSpec;
  onPasses: (passes: CameraPasses) => void;
}) {
  const drawn = useRef<{ snapshot: SceneSnapshot; spec: CameraSpec } | null>(null);
  useFrame(({ gl, scene, camera }) => {
    if (drawn.current?.snapshot !== snapshot || drawn.current.spec !== spec) {
      drawn.current = { snapshot, spec };
      onPasses(renderPasses(gl, scene, camera, spec.width, spec.height));
    }
  });
  return null;
}

/** A pass drawn as a picture, `width` pixels across, over the camera's own. */
function PassPicture({ pixels, width }: { pixels: Uint8ClampedArray<ArrayBuffer>; width: number }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const height = pixels.length / (width * RGBA);
  useEffect(() => {
    canvas.current?.getContext("2d")?.putImageData(new ImageData(pixels, width), 0, 0);
  }, [pixels, width]);
  return (
    <canvas
      ref={canvas}
      className="camera-pass"
      width={width}
      height={height}
      data-testid="camera-pass"
    />
  );
}

/** The camera's field of view across its picture, in degrees. */
export function fieldAcross(spec: CameraSpec): number {
  return MathUtils.radToDeg(2 * Math.atan(spec.width / (2 * spec.fx)));
}

function describePixel(
  passes: CameraPasses | null,
  pixel: { u: number; v: number } | null,
): string {
  if (passes === null) {
    return "Reading the depth and instance passes…";
  }
  if (pixel === null) {
    return "Point at the picture to read what each pixel shows.";
  }
  const { entityId, depth } = passesAt(passes, pixel.u, pixel.v);
  const at = `Pixel (${pixel.u}, ${pixel.v})`;
  return entityId === null || depth === null
    ? `${at}: nothing`
    : `${at}: ${entityId}, ${formatMetres(depth)} m ahead`;
}

/**
 * What a scene's camera sees: the scene drawn from where it stands, with its
 * intrinsics, as its picture; and its depth and instance passes, drawn apart
 * from it at its own size. Pointing at the picture reads, at that pixel, the
 * entity it shows and how far ahead it lies. The picture's drawing is kept,
 * so that a test can read its pixels.
 */
export function CameraView({ snapshot, spec }: { snapshot: SceneSnapshot; spec: CameraSpec }) {
  const [pass, setPass] = useState<Pass>("rgb");
  const [passes, setPasses] = useState<CameraPasses | null>(null);
  const [pixel, setPixel] = useState<{ u: number; v: number } | null>(null);
  const height = (VIEW_WIDTH_PX * spec.height) / spec.width;
  const range = passes === null ? null : depthRange(passes);
  // Drawn once for each new pass, not as the pointer moves.
  const picture = useMemo(() => {
    if (passes === null || pass === "rgb") {
      return null;
    }
    return pass === "depth" ? depthPicture(passes) : instancePicture(passes);
  }, [passes, pass]);

  const point = (event: PointerEvent<HTMLDivElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    setPixel({
      u: Math.floor(((event.clientX - box.left) * spec.width) / box.width),
      v: Math.floor(((event.clientY - box.top) * spec.height) / box.height),
    });
  };

  return (
    <section className="camera-panel" aria-label="Camera">
      <p data-testid="camera-intrinsics">
        {spec.cameraId}: {spec.width} × {spec.height} px, {Math.round(fieldAcross(spec))}° across
      </p>
      <div className="camera-tabs" role="tablist" aria-label="Camera passes">
        {PASS_ORDER.map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            aria-selected={pass === name}
            onClick={() => setPass(name)}
          >
            {PASS_LABELS[name]}
          </button>
        ))}
      </div>
      <div
        className="camera-picture"
        style={{ width: VIEW_WIDTH_PX, height }}
        onPointerMove={point}
        onPointerLeave={() => setPixel(null)}
      >
        <Canvas
          gl={{ preserveDrawingBuffer: true }}
          aria-label="Camera view"
          data-testid="camera-view"
        >
          <SensorCamera spec={spec} />
          <PassReader snapshot={snapshot} spec={spec} onPasses={setPasses} />
          <color attach="background" args={[BACKGROUND_COLOR]} />
          <ambientLight intensity={AMBIENT_LIGHT_INTENSITY} />
          <directionalLight position={[SUN.x, SUN.y, SUN.z]} intensity={SUN_INTENSITY} />
          <group rotation={WORLD_TO_VIEWER_ROTATION}>
            <SceneView snapshot={snapshot} />
          </group>
        </Canvas>
        {passes !== null && picture !== null && (
          <PassPicture pixels={picture} width={passes.width} />
        )}
      </div>
      <p data-testid="camera-pixel">{describePixel(passes, pixel)}</p>
      {pass === "depth" && range !== null && (
        <p data-testid="camera-depth-range">
          Depth ahead, on a log scale: white at {formatMetres(range.nearest)} m, black at{" "}
          {formatMetres(range.farthest)} m and where nothing is.
        </p>
      )}
      {pass === "instance" && passes !== null && (
        <ol className="camera-entities" aria-label="Entities in view">
          {passes.inView.map(({ entityId, index, pixels }) => (
            <li key={entityId} data-testid="camera-entity">
              <span
                className="camera-swatch"
                style={{ background: `rgb(${instanceColor(index).join(" ")})` }}
              />
              {entityId}: {formatCount(pixels)} px
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
