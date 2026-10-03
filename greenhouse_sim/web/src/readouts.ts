import type { Point3 } from "./world";

/** What the HUD shows about the 3D view, sampled a few times a second. */
export interface ViewSample {
  framesPerSecond: number;
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

/** A simulated instant as the HUD writes it, in UTC to the minute. */
export function formatInstant(iso: string): string {
  const instant = new Date(iso);
  if (Number.isNaN(instant.getTime())) {
    return iso;
  }
  return `${instant.toISOString().slice(0, ISO_DATE_AND_MINUTES_LENGTH).replace("T", " ")} UTC`;
}
