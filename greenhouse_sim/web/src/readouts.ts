import type { Point3 } from "./world";

/** What the HUD shows about the 3D view, sampled a few times a second. */
export interface ViewSample {
  framesPerSecond: number;
  /** The mean and the longest time from one frame to the next, in milliseconds. */
  frameTimeMs: number;
  worstFrameMs: number;
  /** What the renderer drew in a frame. */
  drawCalls: number;
  triangles: number;
  /** What the renderer holds in GPU memory. */
  geometries: number;
  textures: number;
  /** The page's JavaScript heap in bytes, where the browser reports it (Chromium). */
  heapBytes: number | null;
  camera: Point3;
  objects: number;
}

const MILLISECONDS_PER_SECOND = 1000;
// "2026-01-04T12:00" from an ISO 8601 instant: the date, hours and minutes.
const ISO_DATE_AND_MINUTES_LENGTH = 16;

/** The frame rate over a sampling window, or 0 for an empty window. */
export function framesPerSecond(frames: number, elapsedMs: number): number {
  return elapsedMs > 0 ? (frames * MILLISECONDS_PER_SECOND) / elapsedMs : 0;
}

/** A world position in metres, as the HUD writes it. */
export function formatPoint(point: Point3): string {
  return `x ${formatMetres(point.x)}, y ${formatMetres(point.y)}, z ${formatMetres(point.z)}`;
}

export function formatMetres(value: number): string {
  // Two decimals is centimetres; -0.00 would only be noise.
  const rounded = value.toFixed(2);
  return rounded === "-0.00" ? "0.00" : rounded;
}

// A size under a centimetre, such as a leaflet's thickness or a petiole's
// radius, is written to a tenth of a millimetre, not as nothing.
const SMALL_SIZE_M = 0.01;
const SMALL_SIZE_DECIMALS = 4;

/** A size in metres: to the centimetre, or finer if it is under one. */
export function formatSize(value: number): string {
  return Math.abs(value) < SMALL_SIZE_M ? value.toFixed(SMALL_SIZE_DECIMALS) : formatMetres(value);
}

/** A simulated instant as the HUD writes it, in UTC to the minute. */
export function formatInstant(iso: string): string {
  const instant = new Date(iso);
  if (Number.isNaN(instant.getTime())) {
    return iso;
  }
  return `${instant.toISOString().slice(0, ISO_DATE_AND_MINUTES_LENGTH).replace("T", " ")} UTC`;
}

/** A speed as a multiple of the simulator's own pace, such as `0.5×`. */
export function formatSpeed(speed: number): string {
  return `${speed}×`;
}

// Enough to tell a quaternion's components apart without implying more precision.
const QUATERNION_DECIMALS = 3;
// Property values are shown to the hundredth, as positions are.
const VALUE_DECIMALS = 2;

/** A rotation as the snapshot gives it, a unit quaternion. */
export function formatRotation(rotation: { w: number; x: number; y: number; z: number }): string {
  const parts = (["w", "x", "y", "z"] as const).map(
    (axis) => `${axis} ${rotation[axis].toFixed(QUATERNION_DECIMALS)}`,
  );
  return parts.join(", ");
}

/** A property value as the inspector shows it: whole numbers whole, others to the hundredth. */
export function formatValue(value: string | number | boolean): string {
  if (typeof value !== "number" || Number.isInteger(value)) {
    return String(value);
  }
  return value.toFixed(VALUE_DECIMALS);
}

// Frame times to a tenth of a millisecond: finer is noise.
const FRAME_TIME_DECIMALS = 1;
const BYTES_PER_MEBIBYTE = 1_048_576;

/** A frame's mean and worst time, as the HUD writes them. */
export function formatFrameTime(meanMs: number, worstMs: number): string {
  return `${meanMs.toFixed(FRAME_TIME_DECIMALS)} ms, worst ${worstMs.toFixed(FRAME_TIME_DECIMALS)} ms`;
}

/** A count with thousands separated, such as 12,345, the same in every locale. */
export function formatCount(count: number): string {
  return count.toLocaleString("en-US");
}

/** What the renderer holds, and the page's heap where the browser reports it. */
export function formatMemory(
  geometries: number,
  textures: number,
  heapBytes: number | null,
): string {
  const held = `${formatCount(geometries)} geometries, ${formatCount(textures)} textures`;
  return heapBytes === null
    ? held
    : `${held}, ${formatCount(Math.round(heapBytes / BYTES_PER_MEBIBYTE))} MiB heap`;
}
