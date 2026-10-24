import { SRGBColorSpace, Color as ThreeColor } from "three";

import type {
  Color,
  SceneEntity,
  SceneEntityKind,
  SceneSnapshot,
} from "../scene/generated/snapshotTypes";

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
  "WIRE",
  "OBSTACLE",
] as const satisfies readonly SceneEntityKind[];
export type LayoutCategory = (typeof LAYOUT_CATEGORIES)[number];

/** The greenhouse's climate equipment, by what each piece is for (P14.5):
 * moving air, heating or drying it. A piece of any kind, one the viewer was
 * not built with too, takes the category of what it does, as the scene says
 * it (`properties.does`). */
export const EQUIPMENT_CATEGORIES = ["MOVES_AIR", "HEATS", "DRIES"] as const;
export type EquipmentCategory = (typeof EQUIPMENT_CATEGORIES)[number];
// What a piece does, as the scene names it, by its category.
const DOES: Readonly<Record<string, EquipmentCategory>> = {
  moves_air: "MOVES_AIR",
  heats: "HEATS",
  dries: "DRIES",
};

/** The greenhouse's sensors: point sensors of every kind, and cameras. */
export const SENSOR_CATEGORIES = ["SENSOR", "CAMERA"] as const satisfies readonly SceneEntityKind[];
export type SensorCategory = (typeof SENSOR_CATEGORIES)[number];

export type Category = EnvelopeCategory | LayoutCategory | EquipmentCategory | SensorCategory;

/** A colour per category, each group from a palette that stays distinct for
 * most colour-blind viewers: the envelope's from Okabe-Ito, the layout's from
 * Paul Tol's muted scheme, wires in Okabe-Ito's black, and the equipment's
 * and the sensors' from Tol's bright scheme, as the simulator colours them. */
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
  WIRE: "#000000",
  OBSTACLE: "#dddddd",
  MOVES_AIR: "#4477aa",
  HEATS: "#ee6677",
  DRIES: "#66ccee",
  SENSOR: "#ccbb44",
  CAMERA: "#aa3377",
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
  WIRE: "wire",
  OBSTACLE: "obstacle",
  MOVES_AIR: "moving air",
  HEATS: "heating",
  DRIES: "drying",
  SENSOR: "sensor",
  CAMERA: "camera",
};

const CATEGORIES: readonly Category[] = [
  ...ENVELOPE_CATEGORIES,
  ...LAYOUT_CATEGORIES,
  ...EQUIPMENT_CATEGORIES,
  ...SENSOR_CATEGORIES,
];

// The categories an entity takes by its kind alone.
const KIND_CATEGORIES: readonly SceneEntityKind[] = [
  ...ENVELOPE_CATEGORIES,
  ...LAYOUT_CATEGORIES,
  ...SENSOR_CATEGORIES,
];

function isKindCategory(
  kind: SceneEntityKind,
): kind is EnvelopeCategory | LayoutCategory | SensorCategory {
  return KIND_CATEGORIES.includes(kind);
}

/** An entity's category: a piece of equipment's by what it does, any other's
 * by its kind; null for one that has none, such as a plant. */
export function categoryOf(entity: SceneEntity): Category | null {
  if (entity.kind === "EQUIPMENT") {
    const does = entity.properties.does;
    return typeof does === "string" ? (DOES[does] ?? null) : null;
  }
  return isKindCategory(entity.kind) ? entity.kind : null;
}

export function isEnvelopeCategory(category: Category): category is EnvelopeCategory {
  return (ENVELOPE_CATEGORIES as readonly Category[]).includes(category);
}

export function isEquipmentCategory(category: Category): category is EquipmentCategory {
  return (EQUIPMENT_CATEGORIES as readonly Category[]).includes(category);
}

export function isSensorCategory(category: Category): category is SensorCategory {
  return (SENSOR_CATEGORIES as readonly Category[]).includes(category);
}

/** The colour an entity takes in the categories' debug view, or null for one
 * that is not part of the envelope, layout, equipment or sensors, such as a
 * plant, which keeps its own. */
export function categoryColor(entity: SceneEntity): Color | null {
  const category = categoryOf(entity);
  if (category === null) {
    return null;
  }
  const { r, g, b } = new ThreeColor(CATEGORY_COLORS[category]).getRGB(
    new ThreeColor(),
    SRGBColorSpace,
  );
  return { r, g, b };
}

/** What an entity is, in words: a piece of equipment's kind, as the scene
 * names it; another's category's name, or its kind's. */
export function semanticType(entity: SceneEntity): string {
  const deviceKind = entity.properties.device_kind;
  if (entity.kind === "EQUIPMENT" && typeof deviceKind === "string") {
    return deviceKind.replaceAll("_", " ");
  }
  const category = categoryOf(entity);
  return category === null
    ? entity.kind.toLowerCase().replaceAll("_", " ")
    : CATEGORY_LABELS[category];
}

/** The categories a scene holds, in the legends' order: the envelope's, the
 * layout's, the equipment's, then the sensors'. */
export function categoriesIn(snapshot: SceneSnapshot): Category[] {
  const held = new Set(snapshot.entities.map(categoryOf));
  return CATEGORIES.filter((category) => held.has(category));
}
