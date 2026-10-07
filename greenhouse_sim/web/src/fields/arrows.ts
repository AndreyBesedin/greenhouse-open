import { Matrix4, Quaternion, Vector3 } from "three";

import { type ScalarRange, scalarColor } from "../debug/scalar";
import type { Color } from "../scene/generated/snapshotTypes";
import { type Channel, cellCentre, cellOffset, type EnvironmentField } from "./field";

const MATRIX_SIZE = 16;
// The longest arrow is this share of a cell's smallest side, so neighbours
// never touch.
const LONGEST_SHARE_OF_CELL = 0.9;
// An arrow's shaft is this thick, whatever its length, in metres.
export const ARROW_WIDTH_M = 0.03;
// Slower than this, air is drawn as still: no arrow.
const STILL_M_S = 1e-6;
const UP = new Vector3(0, 0, 1);

/** Arrows over a field, one batch of instances: each instance's placement as
 * a 4x4 matrix, column-major, and its colour. */
export interface FieldArrowInstances {
  matrices: Float32Array;
  colors: Color[];
  /** The speeds the colours run over. */
  range: ScalarRange;
}

/**
 * An arrow at every cell's centre of a vector channel, pointing where the air
 * goes there, centred on the centre, as long as its speed says, up to
 * `LONGEST_SHARE_OF_CELL` of the cell for the fastest, and coloured by its
 * speed. Each places the unit arrow, which stands on its frame's origin along
 * +z, one long and one wide.
 */
export function fieldArrows(
  field: EnvironmentField,
  channel: Channel,
  colours: ScalarRange = { min: channel.minimum, max: channel.maximum },
): FieldArrowInstances {
  const { grid } = field;
  // Lengths always follow the field's own speeds; colours follow `colours`.
  const range = { min: channel.minimum, max: channel.maximum };
  const longest =
    LONGEST_SHARE_OF_CELL * Math.min(grid.cell_size.x, grid.cell_size.y, grid.cell_size.z);
  const matrices: number[] = [];
  const colors: Color[] = [];
  const matrix = new Matrix4();
  const turn = new Quaternion();
  const direction = new Vector3();
  const position = new Vector3();
  const scale = new Vector3();
  for (let k = 0; k < grid.cells.z; k += 1) {
    for (let j = 0; j < grid.cells.y; j += 1) {
      for (let i = 0; i < grid.cells.x; i += 1) {
        const offset = cellOffset(grid, channel, i, j, k);
        direction.set(
          channel.values[offset] ?? 0,
          channel.values[offset + 1] ?? 0,
          channel.values[offset + 2] ?? 0,
        );
        const speed = direction.length();
        if (speed < STILL_M_S) {
          continue;
        }
        direction.divideScalar(speed);
        const length = range.max > 0 ? (longest * speed) / range.max : 0;
        const centre = cellCentre(grid, i, j, k);
        position.set(centre.x, centre.y, centre.z).addScaledVector(direction, -length / 2);
        turn.setFromUnitVectors(UP, direction);
        matrix.compose(position, turn, scale.set(ARROW_WIDTH_M, ARROW_WIDTH_M, length));
        matrices.push(...matrix.toArray());
        colors.push(scalarColor(speed, colours));
      }
    }
  }
  return { matrices: Float32Array.from(matrices), colors, range: colours };
}

export { MATRIX_SIZE };
