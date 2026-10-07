import type { Point3 } from "../world";
import type { SliceAxis, SliceQuantity } from "./display";
import { type EnvironmentField, sample } from "./field";
import type { FieldGrid } from "./generated/fieldTypes";

/** A slice through a field: a grid of points across it, at the cells'
 * corners, `columns` by `rows`, and the quantity's value at each, or null
 * where the field has none. */
export interface SliceValues {
  columns: number;
  rows: number;
  points: Point3[];
  values: (number | null)[];
}

/** The two axes a slice square to `axis` spans, in a right-handed order. */
export function sliceSpans(axis: SliceAxis): [SliceAxis, SliceAxis] {
  switch (axis) {
    case "x":
      return ["y", "z"];
    case "y":
      return ["z", "x"];
    case "z":
      return ["x", "y"];
  }
}

/** Where a slice square to `axis` may lie: the field's box along it. */
export function sliceExtent(grid: FieldGrid, axis: SliceAxis): { min: number; max: number } {
  return {
    min: grid.origin[axis],
    max: grid.origin[axis] + grid.cells[axis] * grid.cell_size[axis],
  };
}

/** A quantity's value at a point: a scalar channel's, or for `speed`, the
 * magnitude of the velocity's. */
export function quantityAt(
  field: EnvironmentField,
  quantity: SliceQuantity,
  point: Point3,
): number | null {
  if (quantity === "speed") {
    const velocity = field.channels.velocity;
    const sampled = velocity === undefined ? null : sample(field.grid, velocity, point);
    return sampled === null ? null : Math.hypot(...sampled);
  }
  const channel = field.channels[quantity];
  const sampled = channel === undefined ? null : sample(field.grid, channel, point);
  return sampled === null ? null : (sampled[0] ?? null);
}

/** The quantity across a slice square to `axis` at `position`, sampled at the
 * corners of the field's cells across it. */
export function sliceValues(
  field: EnvironmentField,
  quantity: SliceQuantity,
  axis: SliceAxis,
  position: number,
): SliceValues {
  const { grid } = field;
  const [across, up] = sliceSpans(axis);
  const columns = grid.cells[across] + 1;
  const rows = grid.cells[up] + 1;
  const points: Point3[] = [];
  const values: (number | null)[] = [];
  for (let row = 0; row < rows; row += 1) {
    for (let column = 0; column < columns; column += 1) {
      const point = { x: 0, y: 0, z: 0 };
      point[axis] = position;
      point[across] = grid.origin[across] + column * grid.cell_size[across];
      point[up] = grid.origin[up] + row * grid.cell_size[up];
      points.push(point);
      values.push(quantityAt(field, quantity, point));
    }
  }
  return { columns, rows, points, values };
}
