import { SRGBColorSpace, Color as ThreeColor } from "three";

import type { Color, SceneEntity, SceneSnapshot } from "../scene/generated/snapshotTypes";

/** A scalar's colours from low to high: viridis, which reads evenly, in
 * greyscale too, and for most colour-blind viewers. */
export const SCALAR_STOPS: readonly string[] = [
  "#440154",
  "#3b528b",
  "#21918c",
  "#5ec962",
  "#fde725",
];

const STOP_COLORS: readonly Color[] = SCALAR_STOPS.map((hex) => {
  const { r, g, b } = new ThreeColor(hex).getRGB(new ThreeColor(), SRGBColorSpace);
  return { r, g, b };
});

export interface ScalarRange {
  min: number;
  max: number;
}

/** Entities shaded by one numeric property, over its range in the scene. */
export interface Colouring {
  property: string;
  range: ScalarRange;
}

export function scalarValue(entity: SceneEntity, property: string): number | null {
  const value = entity.properties[property];
  return typeof value === "number" ? value : null;
}

/** The numeric properties any of the scene's entities has, in alphabetical order. */
export function scalarProperties(snapshot: SceneSnapshot): string[] {
  const names = new Set<string>();
  for (const entity of snapshot.entities) {
    for (const [name, value] of Object.entries(entity.properties)) {
      if (typeof value === "number") {
        names.add(name);
      }
    }
  }
  return [...names].sort();
}

/** How a scene is shaded by `property`, or null if no entity has it. */
export function colouringBy(snapshot: SceneSnapshot, property: string): Colouring | null {
  const values = snapshot.entities
    .map((entity) => scalarValue(entity, property))
    .filter((value) => value !== null);
  if (values.length === 0) {
    return null;
  }
  return { property, range: { min: Math.min(...values), max: Math.max(...values) } };
}

/** Where a value sits in a range, from 0 at the low end to 1 at the high end.
 * A range of a single value puts it in the middle. */
export function scalarPosition(value: number, range: ScalarRange): number {
  const span = range.max - range.min;
  if (span === 0) {
    return 1 / 2;
  }
  return Math.min(Math.max((value - range.min) / span, 0), 1);
}

/** A value's colour in the range, blended between the two nearest stops in sRGB,
 * as the legend's CSS gradient blends them. */
export function scalarColor(value: number, range: ScalarRange): Color {
  const along = scalarPosition(value, range) * (STOP_COLORS.length - 1);
  const index = Math.min(Math.floor(along), STOP_COLORS.length - 2);
  const low = STOP_COLORS[index];
  const high = STOP_COLORS[index + 1];
  if (low === undefined || high === undefined) {
    throw new Error("a scalar scale needs at least two colours");
  }
  const share = along - index;
  return {
    r: low.r + (high.r - low.r) * share,
    g: low.g + (high.g - low.g) * share,
    b: low.b + (high.b - low.b) * share,
  };
}
