import { Color } from "three";

import type { Point3 } from "../world";
import type { Boundary, BoundaryCategory, CfdGeometry, Face } from "./generated/geometryTypes";

/** The categories of a CFD domain's boundaries, in the order a legend lists
 * them. */
export const CFD_CATEGORIES = [
  "floor",
  "wall",
  "ceiling",
  "opening",
  "obstacle",
] as const satisfies readonly BoundaryCategory[];

/** The domain's own faces, which openings are cut in. */
export const FACE_CATEGORIES: ReadonlySet<BoundaryCategory> = new Set(["floor", "wall", "ceiling"]);

/** A colour per category, from Okabe-Ito's palette, which stays distinct for
 * most colour-blind viewers: the floor, walls and ceiling as the categories'
 * view colours the floor, walls and roof, and openings and obstacles in its
 * strongest colours. */
export const CFD_COLORS: Record<BoundaryCategory, string> = {
  floor: "#e69f00",
  wall: "#56b4e9",
  ceiling: "#009e73",
  opening: "#d55e00",
  obstacle: "#cc79a7",
};

export const CFD_LABELS: Record<BoundaryCategory, string> = {
  floor: "floor",
  wall: "wall",
  ceiling: "ceiling, at the eaves",
  opening: "opening",
  obstacle: "obstacle",
};

type Axis = "x" | "y" | "z";

// Each face of the domain: the axis it is square to, and which way along it
// the domain's inside lies.
const FACE_AXES: Record<Face, { axis: Axis; inward: 1 | -1 }> = {
  floor: { axis: "z", inward: 1 },
  ceiling: { axis: "z", inward: -1 },
  wall_front: { axis: "x", inward: 1 },
  wall_back: { axis: "x", inward: -1 },
  wall_right: { axis: "y", inward: 1 },
  wall_left: { axis: "y", inward: -1 },
};
// A face is drawn this far inside the domain, in metres, so that it does not
// fight the scene's own surface in the same place for the same pixels, and
// an opening this far outside it, so that it shows in front of its face and
// of the scene's glazing from the cameras outside.
const FACE_INSET_M = 0.02;
const OPENING_OUTSET_M = 0.03;

/** How a boundary is drawn: a box, or for one on a face, a rectangle square
 * to `normal`. Its size along `normal` is then nothing. */
export interface BoundaryShape {
  name: string;
  category: BoundaryCategory;
  centre: Point3;
  size: Point3;
  normal: Axis | null;
}

export function boundaryShape(boundary: Boundary): BoundaryShape {
  const { minimum, maximum } = boundary.box;
  const centre = {
    x: (minimum.x + maximum.x) / 2,
    y: (minimum.y + maximum.y) / 2,
    z: (minimum.z + maximum.z) / 2,
  };
  const size = {
    x: maximum.x - minimum.x,
    y: maximum.y - minimum.y,
    z: maximum.z - minimum.z,
  };
  if (boundary.face === undefined || boundary.face === null) {
    return { name: boundary.name, category: boundary.category, centre, size, normal: null };
  }
  const { axis, inward } = FACE_AXES[boundary.face];
  const inset = boundary.category === "opening" ? -OPENING_OUTSET_M : FACE_INSET_M;
  return {
    name: boundary.name,
    category: boundary.category,
    centre: { ...centre, [axis]: centre[axis] + inward * inset },
    size,
    normal: axis,
  };
}

const AXES: readonly Axis[] = ["x", "y", "z"];
// A box's eight corners by index: each lies at the low or high end along an
// axis as one bit of its index says, x the lowest bit.
const AXIS_BITS = Object.fromEntries(AXES.map((axis, index) => [axis, 1 << index])) as Record<
  Axis,
  number
>;
const CORNERS = 1 << AXES.length;
// Its twelve edges join each corner to those one bit higher.
const BOX_EDGES: readonly (readonly [number, number])[] = Array.from(
  { length: CORNERS },
  (_, from) =>
    AXES.filter((axis) => !(from & AXIS_BITS[axis])).map(
      (axis) => [from, from | AXIS_BITS[axis]] as const,
    ),
).flat();

function corner(shape: BoundaryShape, index: number): Point3 {
  const along = (axis: Axis) =>
    shape.centre[axis] + ((index & AXIS_BITS[axis] ? 1 : -1) * shape.size[axis]) / 2;
  return { x: along("x"), y: along("y"), z: along("z") };
}

/** Every boundary's outline as line segments, each end coloured by its
 * category in the renderer's linear colours: a flat one's four edges, a
 * box's twelve. */
export function boundaryOutlines(shapes: readonly BoundaryShape[]): {
  positions: Float32Array;
  colors: Float32Array;
} {
  const positions: number[] = [];
  const colors: number[] = [];
  for (const shape of shapes) {
    const color = new Color(CFD_COLORS[shape.category]);
    // A flat shape's far corners are its near ones: only its near side's
    // edges are drawn.
    const far = shape.normal === null ? 0 : AXIS_BITS[shape.normal];
    for (const [from, to] of BOX_EDGES) {
      if ((from | to) & far) {
        continue;
      }
      const start = corner(shape, from);
      const end = corner(shape, to);
      positions.push(start.x, start.y, start.z, end.x, end.y, end.z);
      colors.push(color.r, color.g, color.b, color.r, color.g, color.b);
    }
  }
  return { positions: Float32Array.from(positions), colors: Float32Array.from(colors) };
}

/** What a legend says of each category the geometry has: how many
 * boundaries, and how many of the mesh's faces they are made of, or for
 * obstacles, how many cells they remove. */
export function categorySummary(
  geometry: CfdGeometry,
): { category: BoundaryCategory; boundaries: number; meshFaces: number }[] {
  return CFD_CATEGORIES.flatMap((category) => {
    const of = geometry.boundaries.filter((boundary) => boundary.category === category);
    return of.length === 0
      ? []
      : [
          {
            category,
            boundaries: of.length,
            meshFaces: of.reduce((total, boundary) => total + boundary.mesh_faces, 0),
          },
        ];
  });
}
