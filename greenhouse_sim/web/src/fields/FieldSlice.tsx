import { useEffect, useMemo } from "react";
import { BufferAttribute, BufferGeometry, DoubleSide } from "three";

import { type ScalarRange, scalarColor } from "../debug/scalar";
import { threeColor } from "../scene/ShapeMesh";
import type { Slice } from "./display";
import type { EnvironmentField } from "./field";
import { sliceValues } from "./slice";

const XYZ = 3;
// Where the field says nothing, the slice is grey.
const NOTHING = { r: 0.6, g: 0.6, b: 0.6 };
// A slice lets the scene show through a little.
const SLICE_OPACITY = 0.85;

/** The geometry of a slice through a field: two triangles per cell across
 * it, each corner coloured by the quantity there. */
export function sliceGeometry(
  field: EnvironmentField,
  slice: Slice,
  range: ScalarRange,
): BufferGeometry {
  const { columns, rows, points, values } = sliceValues(
    field,
    slice.quantity,
    slice.axis,
    slice.position,
  );
  const positions = new Float32Array(points.length * XYZ);
  const colors = new Float32Array(points.length * XYZ);
  points.forEach((point, index) => {
    positions.set([point.x, point.y, point.z], index * XYZ);
    const value = values[index];
    // Vertex colours are linear, as the renderer works in.
    const color = threeColor(
      value === null || value === undefined ? NOTHING : scalarColor(value, range),
    );
    colors.set([color.r, color.g, color.b], index * XYZ);
  });
  const triangles: number[] = [];
  for (let row = 0; row + 1 < rows; row += 1) {
    for (let column = 0; column + 1 < columns; column += 1) {
      const corner = row * columns + column;
      triangles.push(corner, corner + 1, corner + columns + 1);
      triangles.push(corner, corner + columns + 1, corner + columns);
    }
  }
  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new BufferAttribute(positions, XYZ));
  geometry.setAttribute("color", new BufferAttribute(colors, XYZ));
  geometry.setIndex(triangles);
  return geometry;
}

/** A slice through a field, coloured by a quantity, seen from either side.
 * Clicks pass through. */
export function FieldSlice({
  field,
  slice,
  range,
}: {
  field: EnvironmentField;
  slice: Slice;
  range: ScalarRange;
}) {
  const geometry = useMemo(() => sliceGeometry(field, slice, range), [field, slice, range]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  return (
    <mesh geometry={geometry} raycast={() => null}>
      <meshBasicMaterial vertexColors side={DoubleSide} transparent opacity={SLICE_OPACITY} />
    </mesh>
  );
}
