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

/** The parts of a greenhouse's layout, by kind: where plants stand, what
 * carries them, the areas kept clear, and the fixtures in the way. */
export const LAYOUT_CATEGORIES = [
  "PLANTING_POSITION",
  "CROP_GUTTER",
  "BENCH",
  "SLAB",
  "WALKWAY",
  "SERVICE_ZONE",
  "KEEP_OUT",
  "RAIL",
  "PIPE",
  "OBSTACLE",
] as const satisfies readonly SceneEntityKind[];
export type LayoutCategory = (typeof LAYOUT_CATEGORIES)[number];

export type Category = EnvelopeCategory | LayoutCategory;

/** A colour per category, each group from a palette that stays distinct for
 * most colour-blind viewers: the envelope's from Okabe-Ito, the layout's from
 * Paul Tol's muted scheme. */
export const CATEGORY_COLORS: Record<Category, string> = {
  FLOOR: "#e69f00",
  WALL: "#56b4e9",
  ROOF: "#009e73",
  VENT: "#f0e442",
  DOOR: "#0072b2",
  GUTTER: "#d55e00",
  FRAME: "#cc79a7",
  PLANTING_POSITION: "#cc6677",
  CROP_GUTTER: "#332288",
  BENCH: "#117733",
  SLAB: "#ddcc77",
  WALKWAY: "#44aa99",
  SERVICE_ZONE: "#88ccee",
  KEEP_OUT: "#882255",
  RAIL: "#999933",
  PIPE: "#aa4499",
  OBSTACLE: "#dddddd",
};

export const CATEGORY_LABELS: Record<Category, string> = {
  FLOOR: "floor",
  WALL: "wall",
  ROOF: "roof",
  VENT: "vent",
  DOOR: "door",
  GUTTER: "gutter",
  FRAME: "frame",
  PLANTING_POSITION: "planting position",
  CROP_GUTTER: "crop gutter",
  BENCH: "bench",
  SLAB: "slab",
  WALKWAY: "walkway",
  SERVICE_ZONE: "service zone",
  KEEP_OUT: "keep-out",
  RAIL: "rail",
  PIPE: "pipe",
  OBSTACLE: "obstacle",
};

const CATEGORIES: readonly Category[] = [...ENVELOPE_CATEGORIES, ...LAYOUT_CATEGORIES];

function isCategory(kind: SceneEntityKind): kind is Category {
  return (CATEGORIES as readonly SceneEntityKind[]).includes(kind);
}

export function isEnvelopeCategory(category: Category): category is EnvelopeCategory {
  return (ENVELOPE_CATEGORIES as readonly Category[]).includes(category);
}

/** The colour a kind takes in the categories' debug view, or null for a kind
 * that is not part of the envelope or layout, such as a plant, which keeps
 * its own. */
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

/** The categories a scene holds, in the legends' order: the envelope's, then
 * the layout's. */
export function categoriesIn(snapshot: SceneSnapshot): Category[] {
  const kinds = new Set(snapshot.entities.map((entity) => entity.kind));
  return CATEGORIES.filter((category) => kinds.has(category));
}
