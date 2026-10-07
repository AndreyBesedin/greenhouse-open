import Ajv2020 from "ajv/dist/2020";

import type { Point3 } from "../world";
import { FIELD_SCHEMA } from "./generated/fieldSchema";
import type {
  AirQuantity,
  ChannelDocument,
  FieldDocument,
  FieldGrid,
} from "./generated/fieldTypes";

// The version of the published field format this viewer reads.
export const SUPPORTED_FIELD_VERSION = 1;
const VECTOR_COMPONENTS = 3;

const validate = new Ajv2020({ allErrors: true, strict: true }).compile<FieldDocument>(
  FIELD_SCHEMA,
);

/** One channel of a field, its values decoded: 32-bit floats running x
 * fastest, then y, then z, a vector's three components fastest of all
 * (`greenhouse_sim/fields/field.py`). */
export interface Channel {
  quantity: AirQuantity;
  unit: string;
  components: 1 | 3;
  values: Float32Array;
  /** The least and greatest value, or magnitude for a vector. */
  minimum: number;
  maximum: number;
}

/** An environment field, checked and decoded. */
export interface EnvironmentField {
  fieldId: string;
  source: string;
  grid: FieldGrid;
  channels: Partial<Record<AirQuantity, Channel>>;
}

export type FieldCheck = { ok: true; field: EnvironmentField } | { ok: false; problems: string[] };

function decode(channel: ChannelDocument, cells: number): Float32Array {
  const bytes = Uint8Array.from(atob(channel.data), (character) => character.charCodeAt(0));
  const values = new Float32Array(bytes.buffer);
  if (values.length !== cells * channel.components) {
    throw new Error(
      `${channel.quantity} has ${values.length} values, not ${cells * channel.components}`,
    );
  }
  return values;
}

/** A published field checked against the schema the simulator publishes,
 * and decoded, rather than trusted. */
export function checkField(body: unknown): FieldCheck {
  if (!validate(body)) {
    const problems = (validate.errors ?? []).map(
      (error) => `${error.instancePath || "the field"} ${error.message ?? "is not valid"}`,
    );
    return { ok: false, problems };
  }
  const { cells } = body.grid;
  const count = cells.x * cells.y * cells.z;
  try {
    const channels: Partial<Record<AirQuantity, Channel>> = {};
    for (const channel of body.channels) {
      channels[channel.quantity] = {
        quantity: channel.quantity,
        unit: channel.unit,
        components: channel.components,
        values: decode(channel, count),
        minimum: channel.minimum,
        maximum: channel.maximum,
      };
    }
    return {
      ok: true,
      field: { fieldId: body.field_id, source: body.source, grid: body.grid, channels },
    };
  } catch (error) {
    return { ok: false, problems: [error instanceof Error ? error.message : String(error)] };
  }
}

/** The centre of cell (i, j, k). */
export function cellCentre(grid: FieldGrid, i: number, j: number, k: number): Point3 {
  return {
    x: grid.origin.x + (i + 1 / 2) * grid.cell_size.x,
    y: grid.origin.y + (j + 1 / 2) * grid.cell_size.y,
    z: grid.origin.z + (k + 1 / 2) * grid.cell_size.z,
  };
}

/** Where cell (i, j, k)'s value starts in a channel's values. */
export function cellOffset(grid: FieldGrid, channel: Channel, i: number, j: number, k: number) {
  return ((k * grid.cells.y + j) * grid.cells.x + i) * channel.components;
}

function corners(coordinate: number, origin: number, size: number, count: number) {
  const position = Math.min(Math.max((coordinate - origin) / size - 1 / 2, 0), count - 1);
  const low = Math.min(Math.floor(position), Math.max(count - 2, 0));
  return { low, high: Math.min(low + 1, count - 1), share: position - low };
}

/** A channel at a point, as the simulator samples it: interpolated between
 * the cells' centres, holding the outermost centres' values out to the box's
 * faces, and nothing (null) outside the box. A vector comes back as its
 * three components, a scalar as one. */
export function sample(grid: FieldGrid, channel: Channel, point: Point3): number[] | null {
  const top = {
    x: grid.origin.x + grid.cells.x * grid.cell_size.x,
    y: grid.origin.y + grid.cells.y * grid.cell_size.y,
    z: grid.origin.z + grid.cells.z * grid.cell_size.z,
  };
  const inside =
    point.x >= grid.origin.x &&
    point.x <= top.x &&
    point.y >= grid.origin.y &&
    point.y <= top.y &&
    point.z >= grid.origin.z &&
    point.z <= top.z;
  if (!inside) {
    return null;
  }
  const x = corners(point.x, grid.origin.x, grid.cell_size.x, grid.cells.x);
  const y = corners(point.y, grid.origin.y, grid.cell_size.y, grid.cells.y);
  const z = corners(point.z, grid.origin.z, grid.cell_size.z, grid.cells.z);
  const result = new Array<number>(channel.components).fill(0);
  for (const [k, wz] of [
    [z.low, 1 - z.share],
    [z.high, z.share],
  ] as const) {
    for (const [j, wy] of [
      [y.low, 1 - y.share],
      [y.high, y.share],
    ] as const) {
      for (const [i, wx] of [
        [x.low, 1 - x.share],
        [x.high, x.share],
      ] as const) {
        const weight = wx * wy * wz;
        const offset = cellOffset(grid, channel, i, j, k);
        for (let c = 0; c < channel.components; c += 1) {
          result[c] = (result[c] ?? 0) + (channel.values[offset + c] ?? 0) * weight;
        }
      }
    }
  }
  return result;
}

export { VECTOR_COMPONENTS };
