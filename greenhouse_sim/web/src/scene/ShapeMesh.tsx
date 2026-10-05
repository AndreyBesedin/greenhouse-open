import { SRGBColorSpace, Color as ThreeColor } from "three";

import { SELECTION_COLOR } from "../debug/overlays";
import type { Color, Shape } from "./generated/snapshotTypes";

// Enough sides for a stem to read as round at greenhouse distances.
export const CYLINDER_SIDES = 24;
// A quarter turn about x stands Three.js's y-aligned cylinder up along z.
export const STAND_UP: [number, number, number] = [Math.PI / 2, 0, 0];
// A selected shape glows in the selection colour, enough to stand out in
// daylight without hiding its own colour.
const HIGHLIGHT_INTENSITY = 0.6;
const NO_GLOW = "#000000";

export function threeColor(color: Color): ThreeColor {
  return new ThreeColor().setRGB(color.r, color.g, color.b, SRGBColorSpace);
}

/** A shape drawn in its own frame, as `world/geometry.py` describes it. Inside
 * the world's z-up group, so world sizes and directions apply directly. */
export function ShapeMesh({
  shape,
  color,
  highlighted = false,
  behindLines = false,
}: {
  shape: Shape;
  color: Color;
  highlighted?: boolean;
  /** Drawn just behind lines at the same depth, such as the ground grid. */
  behindLines?: boolean;
}) {
  const glow = {
    emissive: highlighted ? SELECTION_COLOR : NO_GLOW,
    emissiveIntensity: highlighted ? HIGHLIGHT_INTENSITY : 0,
  };
  switch (shape.shape) {
    case "plane":
      return (
        <mesh>
          <planeGeometry args={[shape.size_x, shape.size_y]} />
          <meshStandardMaterial
            color={threeColor(color)}
            {...glow}
            polygonOffset={behindLines}
            polygonOffsetFactor={1}
            polygonOffsetUnits={1}
          />
        </mesh>
      );
    case "cylinder":
      // Its base is the frame's origin, so lift it by half its height.
      return (
        <mesh position={[0, 0, shape.height / 2]} rotation={STAND_UP}>
          <cylinderGeometry args={[shape.radius, shape.radius, shape.height, CYLINDER_SIDES]} />
          <meshStandardMaterial color={threeColor(color)} {...glow} />
        </mesh>
      );
    case "axes":
      // Lines cannot glow; the selection's bounding box marks it instead.
      return <axesHelper args={[shape.length]} />;
  }
}
