import { SRGBColorSpace, Color as ThreeColor } from "three";

import type { Color, SceneEntityKind, SceneSnapshot } from "../scene/generated/snapshotTypes";

/** The parts of a greenhouse's envelope, by kind: each is a semantic category
 * of its boundary or structure. */
export const ENVELOPE_CATEGORIES = [
  "FLOOR",
  "WALL",
  "ROOF",
  "VENT",
  "DOOR",
  "GUTTER",
  "FRAME",
] as const satisfies readonly SceneEntityKind[];
export type EnvelopeCategory = (typeof ENVELOPE_CATEGORIES)[number];

/** A colour per category from the Okabe-Ito palette, which stays distinct for
 * most colour-blind viewers. */
export const CATEGORY_COLORS: Record<EnvelopeCategory, string> = {
  FLOOR: "#e69f00",
  WALL: "#56b4e9",
  ROOF: "#009e73",
  VENT: "#f0e442",
  DOOR: "#0072b2",
  GUTTER: "#d55e00",
  FRAME: "#cc79a7",
};

export const CATEGORY_LABELS: Record<EnvelopeCategory, string> = {
  FLOOR: "floor",
  WALL: "wall",
  ROOF: "roof",
  VENT: "vent",
  DOOR: "door",
  GUTTER: "gutter",
  FRAME: "frame",
};

function isCategory(kind: SceneEntityKind): kind is EnvelopeCategory {
  return (ENVELOPE_CATEGORIES as readonly SceneEntityKind[]).includes(kind);
}

/** The colour a kind takes in the categories' debug view, or null for a kind
 * that is not part of the envelope, which keeps its own. */
export function categoryColor(kind: SceneEntityKind): Color | null {
  if (!isCategory(kind)) {
    return null;
  }
  const { r, g, b } = new ThreeColor(CATEGORY_COLORS[kind]).getRGB(
    new ThreeColor(),
    SRGBColorSpace,
  );
  return { r, g, b };
}

/** The envelope's categories a scene holds, in the legend's order. */
export function categoriesIn(snapshot: SceneSnapshot): EnvelopeCategory[] {
  const kinds = new Set(snapshot.entities.map((entity) => entity.kind));
  return ENVELOPE_CATEGORIES.filter((category) => kinds.has(category));
}
