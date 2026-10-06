import { useEffect, useMemo } from "react";
import { DoubleSide, EdgesGeometry } from "three";

import { SELECTION_COLOR } from "../debug/overlays";
import type { Box, Color, Plane, Polygon } from "./generated/snapshotTypes";
import { flatGeometry, threeColor } from "./ShapeMesh";

// See-through enough to show everything behind or inside.
const FACE_OPACITY = 0.12;
// Edges are drawn a shade darker than the faces, as a frame.
const EDGE_SHADE = 0.6;

// For an outline that takes no clicks at all.
function passThrough(): void {}

/**
 * A see-through shape with drawn edges, such as glazing or a space's bounds.
 * It stands in its frame as `world/geometry.py` describes the shape: a box on
 * its base, a plane centred on the origin, a polygon at its corners. Its faces
 * and edges are marked see-through, so that a click picks it only when nothing
 * solid lies behind it (`pickEntity`); an outline takes no clicks at all.
 * Selected, its edges take the selection colour.
 */
export function SeeThrough({
  shape,
  color,
  highlighted,
  outlineOnly = false,
}: {
  shape: Box | Plane | Polygon;
  color: Color;
  highlighted: boolean;
  /** Takes no clicks at all, such as bounds lying on a greenhouse's walls. */
  outlineOnly?: boolean;
}) {
  // Rebuilt with each new scene, which for a live scenario is once a day.
  const faces = useMemo(() => flatGeometry(shape), [shape]);
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
  const picking = outlineOnly ? { raycast: passThrough } : { userData: { seeThrough: true } };

  return (
    <group position={[0, 0, lift]}>
      <mesh geometry={faces} {...picking}>
        <meshStandardMaterial
          color={fill}
          transparent
          opacity={FACE_OPACITY}
          depthWrite={false}
          side={DoubleSide}
        />
      </mesh>
      <lineSegments geometry={edges} {...picking}>
        <lineBasicMaterial color={highlighted ? SELECTION_COLOR : frame} />
      </lineSegments>
    </group>
  );
}
