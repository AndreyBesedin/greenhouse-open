import { MathUtils } from "three";

import type { OverlayPrimitive } from "../debug/overlays";
import type { Point3 } from "../world";
import { type EnvironmentField, sample } from "./field";
import type { AirQuantity } from "./generated/fieldTypes";

/** A field holds at most this many probes at once. */
export const MAX_PROBES = 8;
// A probe is written x:y:z, and probes are written one after another, by
// commas: `3:3.2:0.75,7:3.2:0.75`.
const PROBE_PARTS = 3;
// Air slower than this has no direction worth comparing, in metres a second.
const STILL_AIR_M_S = 1e-6;
// Probes are marked in a colour of their own, from ColorBrewer's Dark2.
const PROBE_COLOR = "#e7298a";
// A probe's name floats this far above it, in metres.
const NAME_RISE_M = 0.15;
// A probe's arrow is this long, in metres, where the air is the field's
// fastest, and shorter in proportion where it is slower.
const FASTEST_ARROW_M = 1;

/** The scalar quantities a field may hold. */
export type ScalarQuantity = Exclude<AirQuantity, "velocity">;

/** What a field says at a probe: the air's velocity and speed, and each of
 * its scalars. All of them are null outside the field's box. */
export interface Reading {
  velocity: Point3 | null;
  speed: number | null;
  scalars: Partial<Record<ScalarQuantity, number>>;
}

/** How a reading differs from another's: how much faster the air is, how
 * far its direction turns, in degrees, and how much more of each scalar
 * both hold. Each is null where either says nothing. */
export interface Difference {
  speed: number | null;
  turnDeg: number | null;
  scalars: Partial<Record<ScalarQuantity, number>>;
}

export function probesFrom(text: string | null): Point3[] | undefined {
  if (text === null || text === "") {
    return undefined;
  }
  const probes: Point3[] = [];
  for (const part of text.split(",")) {
    const numbers = part.split(":").map((value) => (value === "" ? Number.NaN : Number(value)));
    const [x, y, z] = numbers;
    if (
      numbers.length !== PROBE_PARTS ||
      x === undefined ||
      y === undefined ||
      z === undefined ||
      !numbers.every(Number.isFinite)
    ) {
      return undefined;
    }
    probes.push({ x, y, z });
  }
  return probes.slice(0, MAX_PROBES);
}

export function probesText(probes: readonly Point3[]): string {
  return probes.map(({ x, y, z }) => `${x}:${y}:${z}`).join(",");
}

/** What a field says at a point, as the simulator would sample it. */
export function readingAt(field: EnvironmentField, point: Point3): Reading {
  const velocityChannel = field.channels.velocity;
  const v = velocityChannel === undefined ? null : sample(field.grid, velocityChannel, point);
  const velocity = v === null ? null : { x: v[0] ?? 0, y: v[1] ?? 0, z: v[2] ?? 0 };
  const scalars: Partial<Record<ScalarQuantity, number>> = {};
  for (const [quantity, channel] of Object.entries(field.channels)) {
    if (quantity === "velocity" || channel === undefined) {
      continue;
    }
    const value = sample(field.grid, channel, point);
    if (value !== null && value[0] !== undefined) {
      scalars[quantity as ScalarQuantity] = value[0];
    }
  }
  return {
    velocity,
    speed: velocity === null ? null : Math.hypot(velocity.x, velocity.y, velocity.z),
    scalars,
  };
}

/** How `reading` differs from `other`. */
export function difference(reading: Reading, other: Reading): Difference {
  const scalars: Partial<Record<ScalarQuantity, number>> = {};
  for (const [quantity, value] of Object.entries(reading.scalars)) {
    const theirs = other.scalars[quantity as ScalarQuantity];
    if (theirs !== undefined) {
      scalars[quantity as ScalarQuantity] = value - theirs;
    }
  }
  const a = reading.velocity;
  const b = other.velocity;
  const speeds = reading.speed !== null && other.speed !== null;
  const moving =
    speeds && (reading.speed ?? 0) > STILL_AIR_M_S && (other.speed ?? 0) > STILL_AIR_M_S;
  let turnDeg: number | null = null;
  if (a !== null && b !== null && moving) {
    const cosine =
      (a.x * b.x + a.y * b.y + a.z * b.z) / ((reading.speed ?? 1) * (other.speed ?? 1));
    turnDeg = MathUtils.radToDeg(Math.acos(Math.min(1, Math.max(-1, cosine))));
  }
  return {
    speed: speeds ? (reading.speed ?? 0) - (other.speed ?? 0) : null,
    turnDeg,
    scalars,
  };
}

/** Where a new probe goes when none is clicked: the middle of the field, at
 * its middle height. */
export function middleOf(field: EnvironmentField): Point3 {
  const { origin, cell_size: size, cells } = field.grid;
  return {
    x: origin.x + (cells.x * size.x) / 2,
    y: origin.y + (cells.y * size.y) / 2,
    z: origin.z + (cells.z * size.z) / 2,
  };
}

/** Each probe as the view marks it: a leader up from the ground under it, a
 * point, its name above it, and an arrow along the air there, as long as the
 * air is fast. */
export function probeOverlays(
  probes: readonly Point3[],
  field: EnvironmentField,
): OverlayPrimitive[] {
  const fastest = field.channels.velocity?.maximum ?? 0;
  return probes.flatMap((probe, index) => {
    const name = `P${index + 1}`;
    const marks: OverlayPrimitive[] = [
      {
        id: `${name}-leader`,
        kind: "line",
        from: { ...probe, z: 0 },
        to: probe,
        color: PROBE_COLOR,
      },
      { id: `${name}-point`, kind: "point", position: probe, color: PROBE_COLOR },
      {
        id: `${name}-name`,
        kind: "label",
        position: { ...probe, z: probe.z + NAME_RISE_M },
        text: name,
      },
    ];
    const { velocity, speed } = readingAt(field, probe);
    if (velocity !== null && speed !== null && speed > STILL_AIR_M_S && fastest > 0) {
      marks.push({
        id: `${name}-air`,
        kind: "arrow",
        origin: probe,
        direction: velocity,
        length: (FASTEST_ARROW_M * speed) / fastest,
        color: PROBE_COLOR,
      });
    }
    return marks;
  });
}
