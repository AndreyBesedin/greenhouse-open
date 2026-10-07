import type { Point3 } from "../world";
import { type Channel, cellCentre, type EnvironmentField, sample } from "./field";

// Streamlines start at every this many cells' centres along each axis, or
// further apart in a field so big that there would be more than
// `MAX_SEEDS` of them: tracing them all takes time in proportion.
export const SEED_EVERY_CELLS = 3;
export const MAX_SEEDS = 300;
// Each step is this share of a cell's smallest side.
const STEP_SHARE_OF_CELL = 0.5;
// A streamline runs at most this many steps each way from its seed.
export const MAX_STEPS = 400;
// Slower than this, the air is still: a streamline stops.
const STILL_M_S = 1e-6;
// A streamline that comes back within this share of a step of its seed has
// closed its loop, and stops.
const CLOSE_SHARE_OF_STEP = 0.5;
// It must have gone at least this many steps before it can close.
const LEAST_STEPS_TO_CLOSE = 8;
// A fourth-order Runge-Kutta step weighs its four headings 1, 2, 2 and 1.
const RUNGE_KUTTA_WEIGHTS = 6;

/** One streamline: its points in order, along the flow, and the air's speed
 * at each. */
export interface Streamline {
  points: Point3[];
  speeds: number[];
}

function along(point: Point3, direction: readonly number[], distance: number): Point3 {
  return {
    x: point.x + (direction[0] ?? 0) * distance,
    y: point.y + (direction[1] ?? 0) * distance,
    z: point.z + (direction[2] ?? 0) * distance,
  };
}

/** Where the air goes at a point, as a unit vector, and how fast; null where
 * the field says nothing or the air is still. */
function heading(
  field: EnvironmentField,
  channel: Channel,
  point: Point3,
): { direction: number[]; speed: number } | null {
  const velocity = sample(field.grid, channel, point);
  if (velocity === null) {
    return null;
  }
  const speed = Math.hypot(...velocity);
  return speed < STILL_M_S ? null : { direction: velocity.map((v) => v / speed), speed };
}

/** One way from a seed, forward along the flow (+1) or back against it (-1),
 * by fourth-order Runge-Kutta steps of equal length. */
function trace(
  field: EnvironmentField,
  channel: Channel,
  seed: Point3,
  sense: 1 | -1,
  step: number,
): Streamline & { closed: boolean } {
  const points: Point3[] = [];
  const speeds: number[] = [];
  let point = seed;
  for (let taken = 0; taken < MAX_STEPS; taken += 1) {
    const first = heading(field, channel, point);
    if (first === null) {
      break;
    }
    points.push(point);
    speeds.push(first.speed);
    const h = sense * step;
    const second = heading(field, channel, along(point, first.direction, h / 2));
    const third = second && heading(field, channel, along(point, second.direction, h / 2));
    const fourth = third && heading(field, channel, along(point, third.direction, h));
    if (second === null || third === null || fourth === null) {
      break;
    }
    const direction = first.direction.map(
      (d1, axis) =>
        (d1 +
          2 * (second.direction[axis] ?? 0) +
          2 * (third.direction[axis] ?? 0) +
          (fourth.direction[axis] ?? 0)) /
        RUNGE_KUTTA_WEIGHTS,
    );
    point = along(point, direction, h);
    const home = Math.hypot(point.x - seed.x, point.y - seed.y, point.z - seed.z);
    if (taken >= LEAST_STEPS_TO_CLOSE && home < CLOSE_SHARE_OF_STEP * step) {
      points.push(seed);
      speeds.push(speeds[0] ?? first.speed);
      return { points, speeds, closed: true };
    }
  }
  return { points, speeds, closed: false };
}

/** How many cells apart a field's seeds are: `SEED_EVERY_CELLS`, or further
 * apart, so that there are at most `MAX_SEEDS`. */
export function seedSpacing(cells: { x: number; y: number; z: number }): number {
  let spacing = SEED_EVERY_CELLS;
  const seeds = (every: number) =>
    Math.ceil(cells.x / every) * Math.ceil(cells.y / every) * Math.ceil(cells.z / every);
  while (seeds(spacing) > MAX_SEEDS) {
    spacing += 1;
  }
  return spacing;
}

/**
 * Streamlines through a vector channel: from seeds at every few cells'
 * centres (`seedSpacing`), traced both ways until the air leaves
 * the field, stands still, comes back to the seed (closing a loop, which is
 * then traced only once), or `MAX_STEPS` are taken.
 * Each runs from its furthest point upstream to its furthest downstream.
 */
export function streamlines(field: EnvironmentField, channel: Channel): Streamline[] {
  const { grid } = field;
  const step = STEP_SHARE_OF_CELL * Math.min(grid.cell_size.x, grid.cell_size.y, grid.cell_size.z);
  const lines: Streamline[] = [];
  const every = seedSpacing(grid.cells);
  const first = Math.floor(every / 2);
  for (let k = first; k < grid.cells.z; k += every) {
    for (let j = first; j < grid.cells.y; j += every) {
      for (let i = first; i < grid.cells.x; i += every) {
        const seed = cellCentre(grid, i, j, k);
        const ahead = trace(field, channel, seed, 1, step);
        // A loop closed downstream needs no tracing back.
        const behind = ahead.closed
          ? { points: [], speeds: [] }
          : trace(field, channel, seed, -1, step);
        // Upstream, reversed, then downstream, the seed once.
        const points = [...behind.points.slice(1).reverse(), ...ahead.points];
        const speeds = [...behind.speeds.slice(1).reverse(), ...ahead.speeds];
        if (points.length >= 2) {
          lines.push({ points, speeds });
        }
      }
    }
  }
  return lines;
}
