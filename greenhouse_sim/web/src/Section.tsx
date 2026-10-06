import { useThree } from "@react-three/fiber";
import { useEffect } from "react";
import { Plane, Vector3 } from "three";

import { type Point3, worldToViewer } from "./world";

/** A cut through the view: what lies on the side `normal` points to, within
 * `distance` of the origin along it, is kept; the rest is cut away. In world
 * coordinates. */
export interface SectionPlane {
  normal: Point3;
  distance: number;
}

/** Cuts everything the renderer draws by a plane, while it is set. */
export function Section({ plane }: { plane: SectionPlane | null }) {
  const gl = useThree((state) => state.gl);

  useEffect(() => {
    if (plane === null) {
      return;
    }
    const normal = worldToViewer(plane.normal);
    gl.clippingPlanes = [new Plane(new Vector3(normal.x, normal.y, normal.z), plane.distance)];
    return () => {
      gl.clippingPlanes = [];
    };
  }, [gl, plane]);

  return null;
}
