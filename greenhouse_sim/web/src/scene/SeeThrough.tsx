import { useEffect, useMemo } from "react";
import { BoxGeometry, type BufferGeometry, DoubleSide, EdgesGeometry, PlaneGeometry } from "three";

import { SELECTION_COLOR } from "../debug/overlays";
import type { Box, Color, Plane } from "./generated/snapshotTypes";
import { threeColor } from "./ShapeMesh";

// See-through enough to show everything behind or inside.
const FACE_OPACITY = 0.12;
// Edges are drawn a shade darker than the faces, as a frame.
const EDGE_SHADE = 0.6;

// Faces that clicks pass through, so a see-through shape never hides what is
// behind or inside it from a pick; its edges can still be clicked.
function passThrough(): void {}

function geometryOf(shape: Box | Plane): BufferGeometry {
  return shape.shape === "box"
    ? new BoxGeometry(shape.size_x, shape.size_y, shape.size_z)
    : new PlaneGeometry(shape.size_x, shape.size_y);
}

/**
 * A see-through box or plane with drawn edges, such as glazing or a space's
 * bounds. It stands in its frame as `world/geometry.py` describes the shape: a
 * box on its base, a plane centred on the origin. Its edges take clicks unless
 * it is only an outline; selected, they take the selection colour.
 */
export function SeeThrough({
  shape,
  color,
  highlighted,
  outlineOnly = false,
}: {
  shape: Box | Plane;
  color: Color;
  highlighted: boolean;
  /** Takes no clicks at all, such as bounds lying on a greenhouse's walls. */
  outlineOnly?: boolean;
}) {
  // Rebuilt with each new scene, which for a live scenario is once a day.
  const faces = useMemo(() => geometryOf(shape), [shape]);
  const edges = useMemo(() => new EdgesGeometry(faces), [faces]);
  useEffect(
    () => () => {
      faces.dispose();
      edges.dispose();
    },
    [faces, edges],
  );
  const fill = threeColor(color);
  const frame = fill.clone().multiplyScalar(EDGE_SHADE);
  const lift = shape.shape === "box" ? shape.size_z / 2 : 0;

  return (
    <group position={[0, 0, lift]}>
      <mesh geometry={faces} raycast={passThrough}>
        <meshStandardMaterial
          color={fill}
          transparent
          opacity={FACE_OPACITY}
          depthWrite={false}
          side={DoubleSide}
        />
      </mesh>
      <lineSegments geometry={edges} {...(outlineOnly ? { raycast: passThrough } : {})}>
        <lineBasicMaterial color={highlighted ? SELECTION_COLOR : frame} />
      </lineSegments>
    </group>
  );
}
