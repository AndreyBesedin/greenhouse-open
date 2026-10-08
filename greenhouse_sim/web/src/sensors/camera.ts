import type { OverlayPrimitive } from "../debug/overlays";
import type { SceneEntity, SceneSnapshot } from "../scene/generated/snapshotTypes";
import type { Point3 } from "../world";

/**
 * A camera as a scene describes it, and its picture as the simulator projects
 * it (`greenhouse_sim.world.sensors.Camera`): in its own frame, x along the
 * way it looks, y to its left, z up, a point at (x, y, z) lands on pixel
 * (ppx − fx y / x, ppy − fy z / x), u to the right and v down its picture.
 */
export interface CameraSpec {
  cameraId: string;
  eye: Point3;
  target: Point3;
  width: number;
  height: number;
  fx: number;
  fy: number;
  ppx: number;
  ppy: number;
}

// The frustum is drawn this far out from the camera, in metres.
export const FRUSTUM_DEPTH_M = 1.5;
// In Tol's purple, as the camera itself.
const FRUSTUM_COLOR = "#aa3377";
const UP: Point3 = { x: 0, y: 0, z: 1 };

function minus(a: Point3, b: Point3): Point3 {
  return { x: a.x - b.x, y: a.y - b.y, z: a.z - b.z };
}

function dot(a: Point3, b: Point3): number {
  return a.x * b.x + a.y * b.y + a.z * b.z;
}

function cross(a: Point3, b: Point3): Point3 {
  return { x: a.y * b.z - a.z * b.y, y: a.z * b.x - a.x * b.z, z: a.x * b.y - a.y * b.x };
}

function unit(a: Point3): Point3 {
  const length = Math.sqrt(dot(a, a));
  return { x: a.x / length, y: a.y / length, z: a.z / length };
}

/** A scene's camera entity as a camera, or null for any other entity. */
export function cameraOf(entity: SceneEntity): CameraSpec | null {
  const p = entity.properties;
  const numbers = [
    p.eye_x,
    p.eye_y,
    p.eye_z,
    p.target_x,
    p.target_y,
    p.target_z,
    p.image_width_px,
    p.image_height_px,
    p.fx_px,
    p.fy_px,
    p.ppx_px,
    p.ppy_px,
  ];
  if (entity.kind !== "CAMERA" || !numbers.every((value) => typeof value === "number")) {
    return null;
  }
  const [ex, ey, ez, tx, ty, tz, width, height, fx, fy, ppx, ppy] = numbers as number[];
  return {
    cameraId: String(p.sensor_id ?? entity.entity_id),
    eye: { x: ex ?? 0, y: ey ?? 0, z: ez ?? 0 },
    target: { x: tx ?? 0, y: ty ?? 0, z: tz ?? 0 },
    width: width ?? 0,
    height: height ?? 0,
    fx: fx ?? 1,
    fy: fy ?? 1,
    ppx: ppx ?? 0,
    ppy: ppy ?? 0,
  };
}

/** The camera's axes in the world: along the way it looks, to its left, kept
 * level, and up its picture. */
export function cameraBasis(spec: CameraSpec): { forward: Point3; left: Point3; up: Point3 } {
  const forward = unit(minus(spec.target, spec.eye));
  const level = cross(UP, forward);
  const left = dot(level, level) > 0 ? unit(level) : { x: 0, y: 1, z: 0 };
  return { forward, left, up: cross(forward, left) };
}

/** Where a point lands on the camera's picture, in pixels from its top left
 * corner, or null if it lies behind the camera. */
export function project(spec: CameraSpec, point: Point3): { u: number; v: number } | null {
  const { forward, left, up } = cameraBasis(spec);
  const offset = minus(point, spec.eye);
  const ahead = dot(offset, forward);
  if (ahead <= 0) {
    return null;
  }
  return {
    u: spec.ppx - (spec.fx * dot(offset, left)) / ahead,
    v: spec.ppy - (spec.fy * dot(offset, up)) / ahead,
  };
}

/** The point of the world a pixel shows at a distance ahead of the camera. */
export function pixelAt(spec: CameraSpec, u: number, v: number, ahead: number): Point3 {
  const { forward, left, up } = cameraBasis(spec);
  const sideways = (-(u - spec.ppx) / spec.fx) * ahead;
  const upwards = (-(v - spec.ppy) / spec.fy) * ahead;
  return {
    x: spec.eye.x + forward.x * ahead + left.x * sideways + up.x * upwards,
    y: spec.eye.y + forward.y * ahead + left.y * sideways + up.y * upwards,
    z: spec.eye.z + forward.z * ahead + left.z * sideways + up.z * upwards,
  };
}

/** Every camera's frustum, as lines from its eye to its picture's corners at
 * `FRUSTUM_DEPTH_M`, and around them. */
export function frustumOverlays(snapshot: SceneSnapshot): OverlayPrimitive[] {
  return snapshot.entities.flatMap((entity) => {
    const spec = cameraOf(entity);
    if (spec === null) {
      return [];
    }
    const corners = [
      pixelAt(spec, 0, 0, FRUSTUM_DEPTH_M),
      pixelAt(spec, spec.width, 0, FRUSTUM_DEPTH_M),
      pixelAt(spec, spec.width, spec.height, FRUSTUM_DEPTH_M),
      pixelAt(spec, 0, spec.height, FRUSTUM_DEPTH_M),
    ];
    return corners.flatMap((corner, index): OverlayPrimitive[] => [
      {
        id: `${spec.cameraId}-ray-${index}`,
        kind: "line",
        from: spec.eye,
        to: corner,
        color: FRUSTUM_COLOR,
      },
      {
        id: `${spec.cameraId}-edge-${index}`,
        kind: "line",
        from: corner,
        to: corners[(index + 1) % corners.length] ?? corner,
        color: FRUSTUM_COLOR,
      },
    ]);
  });
}
