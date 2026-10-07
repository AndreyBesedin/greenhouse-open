import type { ScalarRange } from "../debug/scalar";
import type { Slice, SliceQuantity } from "./display";
import type { EnvironmentField } from "./field";
import { sliceExtent } from "./slice";

/** The quantities a slice through a field can be coloured by: the air's
 * speed if it has a velocity, and each of its scalars. */
export function sliceQuantities(field: EnvironmentField): SliceQuantity[] {
  const quantities: SliceQuantity[] = field.channels.velocity === undefined ? [] : ["speed"];
  for (const channel of Object.values(field.channels)) {
    if (channel !== undefined && channel.quantity !== "velocity") {
      quantities.push(channel.quantity);
    }
  }
  return quantities;
}

/** The slice drawn when none is asked for: the field's first scalar, or its
 * speed, across its middle height. */
export function defaultSlice(field: EnvironmentField): Slice {
  const [, firstScalar] = sliceQuantities(field);
  const quantity = firstScalar ?? sliceQuantities(field)[0] ?? "speed";
  const { min, max } = sliceExtent(field.grid, "z");
  return { quantity, axis: "z", position: (min + max) / 2 };
}

/** What a quantity's colours mean: its title, its unit, and the field's own
 * range for it, or null if the field lacks it. */
export function quantityScale(
  field: EnvironmentField,
  quantity: SliceQuantity,
): { title: string; unit: string; range: ScalarRange } | null {
  const channel = quantity === "speed" ? field.channels.velocity : field.channels[quantity];
  if (channel === undefined) {
    return null;
  }
  return {
    title: quantity === "speed" ? "air speed" : quantity,
    unit: channel.unit,
    range: { min: channel.minimum, max: channel.maximum },
  };
}
