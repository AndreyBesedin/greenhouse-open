import { useThree } from "@react-three/fiber";
import { useEffect, useMemo } from "react";
import { BufferAttribute, BufferGeometry } from "three";
import { LineMaterial } from "three/examples/jsm/lines/LineMaterial.js";
import { LineSegments2 } from "three/examples/jsm/lines/LineSegments2.js";
import { LineSegmentsGeometry } from "three/examples/jsm/lines/LineSegmentsGeometry.js";

import { type ScalarRange, scalarColor } from "../debug/scalar";
import { threeColor } from "../scene/ShapeMesh";
import type { Channel, EnvironmentField } from "./field";
import { streamlines } from "./streamlines";

const RGB = 3;
// Streamlines are this wide on screen, whatever their distance.
const STREAMLINE_WIDTH_PX = 2.5;
// A streamline is traced in half-cell steps, and drawn a cell at a time: a
// segment for every second step, which halves what a software renderer, such
// as a browser test's, draws on a big house's field.
export const STEPS_PER_SEGMENT = 2;

/** The points a streamline is drawn through, by index: every
 * `STEPS_PER_SEGMENT`th from its first, and its last. */
export function drawnPoints(count: number): number[] {
  const drawn: number[] = [];
  for (let index = 0; index < count - 1; index += STEPS_PER_SEGMENT) {
    drawn.push(index);
  }
  return count === 0 ? drawn : [...drawn, count - 1];
}

/** The geometry of a field's streamlines, each streamline as line segments
 * through every few of its steps (`drawnPoints`), each end coloured by the
 * air's speed there. */
export function streamlineGeometry(
  field: EnvironmentField,
  channel: Channel,
  range: ScalarRange,
): BufferGeometry {
  const positions: number[] = [];
  const colors: number[] = [];
  for (const line of streamlines(field, channel)) {
    const drawn = drawnPoints(line.points.length);
    for (let index = 1; index < drawn.length; index += 1) {
      for (const end of [drawn[index - 1] ?? 0, drawn[index] ?? 0]) {
        const point = line.points[end];
        // Vertex colours are linear, as the renderer works in.
        const color = threeColor(scalarColor(line.speeds[end] ?? 0, range));
        if (point !== undefined) {
          positions.push(point.x, point.y, point.z);
          colors.push(color.r, color.g, color.b);
        }
      }
    }
  }
  const geometry = new BufferGeometry();
  geometry.setAttribute("position", new BufferAttribute(Float32Array.from(positions), RGB));
  geometry.setAttribute("color", new BufferAttribute(Float32Array.from(colors), RGB));
  return geometry;
}

/** A field's air velocity as streamlines, coloured by speed, drawn
 * `STREAMLINE_WIDTH_PX` wide on screen, in one draw call. Clicks pass
 * through. */
export function FieldStreamlines({
  field,
  range,
}: {
  field: EnvironmentField;
  range: ScalarRange;
}) {
  const size = useThree((state) => state.size);
  const velocity = field.channels.velocity;
  const lines = useMemo(() => {
    if (velocity === undefined) {
      return null;
    }
    const plain = streamlineGeometry(field, velocity, range);
    const geometry = new LineSegmentsGeometry()
      .setPositions(plain.getAttribute("position").array as Float32Array)
      .setColors(plain.getAttribute("color").array as Float32Array);
    plain.dispose();
    const material = new LineMaterial({ linewidth: STREAMLINE_WIDTH_PX, vertexColors: true });
    const segments = new LineSegments2(geometry, material);
    segments.raycast = () => undefined;
    return segments;
  }, [field, velocity, range]);
  useEffect(
    () => () => {
      lines?.geometry.dispose();
      lines?.material.dispose();
    },
    [lines],
  );
  useEffect(() => {
    lines?.material.resolution.set(size.width, size.height);
  }, [lines, size]);
  return lines === null ? null : <primitive object={lines} />;
}
