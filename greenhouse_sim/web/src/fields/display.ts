import type { AirQuantity } from "./generated/fieldTypes";

/** How a field is drawn: arrows at its cells, streamlines through it, or a
 * slice through it coloured by one quantity. */
export const FIELD_VIEWS = ["arrows", "streamlines", "slice"] as const;
export type FieldView = (typeof FIELD_VIEWS)[number];

/** What a slice is coloured by: one of a field's scalar quantities, or the
 * air's speed, its velocity's magnitude. */
export type SliceQuantity = Exclude<AirQuantity, "velocity"> | "speed";
export const SLICE_AXES = ["x", "y", "z"] as const;
export type SliceAxis = (typeof SLICE_AXES)[number];

/** A plane through a field, square to an axis, at a position along it in
 * metres, coloured by a quantity. */
export interface Slice {
  quantity: SliceQuantity;
  axis: SliceAxis;
  position: number;
}

const SLICE_QUANTITIES: ReadonlySet<string> = new Set<SliceQuantity>([
  "speed",
  "temperature",
  "humidity",
  "co2",
  "pressure",
  "par",
  "irradiance",
]);
// The quantities named otherwise than the field names them.
const TITLES: Partial<Record<SliceQuantity, string>> = { speed: "air speed", par: "PAR" };

/** A quantity as the viewer names it: "air speed", "PAR", "temperature". */
export function quantityTitle(quantity: SliceQuantity): string {
  return TITLES[quantity] ?? quantity;
}
// A slice is written quantity:axis:position, as `temperature:z:1.75`.
const SLICE_PARTS = 3;

export function fieldViewFrom(text: string | null): FieldView | undefined {
  return (FIELD_VIEWS as readonly string[]).includes(text ?? "") ? (text as FieldView) : undefined;
}

export function sliceFrom(text: string | null): Slice | undefined {
  const parts = (text ?? "").split(":");
  const [quantity, axis, position] = parts;
  const at = Number(position);
  if (
    parts.length !== SLICE_PARTS ||
    quantity === undefined ||
    !SLICE_QUANTITIES.has(quantity) ||
    !(SLICE_AXES as readonly string[]).includes(axis ?? "") ||
    position === "" ||
    !Number.isFinite(at)
  ) {
    return undefined;
  }
  return { quantity: quantity as SliceQuantity, axis: axis as SliceAxis, position: at };
}

export function sliceText(slice: Slice): string {
  return `${slice.quantity}:${slice.axis}:${slice.position}`;
}
