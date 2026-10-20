import { useThree } from "@react-three/fiber";
import { useEffect, useRef } from "react";
import { Plane, Raycaster, Vector2, Vector3 } from "three";

import type { Offset } from "./scene/moves";
import { type Point3, viewerToWorld } from "./world";

/** What a drag in the view does to the item being moved (#209). */
export interface MoveDragging {
  /** The item's height, in metres, the level the drag runs along. */
  heightM: number;
  /** The move as the item may make it: snapped, and kept inside the house. */
  shape: (by: Offset) => Offset;
  /** Each step of a drag, and null when one is cancelled. */
  onDrag: (by: Offset | null) => void;
  /** The move a drag made as its button was let go, or null if it made none. */
  onDrop: (by: Offset | null) => void;
}

/**
 * Drags in the view move the item being moved, from wherever they start, as
 * far as the pointer goes along the level of the item's height: an item
 * dragged by itself stays under the pointer. Escape cancels a drag, as does
 * the pointer lost; the view's orbit and pan stand aside meanwhile
 * (`CameraRig`'s `still`).
 */
export function MoveDrag({ heightM, shape, onDrag, onDrop }: MoveDragging) {
  const camera = useThree((state) => state.camera);
  const gl = useThree((state) => state.gl);
  // The latest of what a drag tells, so that one under way keeps going as
  // the page re-renders.
  const told = useRef({ shape, onDrag, onDrop });
  told.current = { shape, onDrag, onDrop };

  useEffect(() => {
    const element = gl.domElement;
    const raycaster = new Raycaster();
    // The level, in the viewer's axes, whose y is the world's z.
    const level = new Plane(new Vector3(0, 1, 0), -heightM);
    // Where the drag under way started, by which pointer, and the move it
    // has made so far.
    let drag: { from: Point3; pointerId: number; by: Offset | null } | null = null;

    function under(event: PointerEvent): Point3 | null {
      const box = element.getBoundingClientRect();
      if (box.width === 0 || box.height === 0) {
        return null;
      }
      const pointer = new Vector2(
        ((event.clientX - box.left) / box.width) * 2 - 1,
        1 - ((event.clientY - box.top) / box.height) * 2,
      );
      camera.updateMatrixWorld();
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.ray.intersectPlane(level, new Vector3());
      return hit === null ? null : viewerToWorld(hit);
    }
    function down(event: PointerEvent): void {
      if (event.button !== 0 || drag !== null) {
        return;
      }
      const from = under(event);
      if (from !== null) {
        drag = { from, pointerId: event.pointerId, by: null };
      }
    }
    function move(event: PointerEvent): void {
      const to = drag === null || event.pointerId !== drag.pointerId ? null : under(event);
      if (drag === null || to === null) {
        return;
      }
      drag.by = told.current.shape({ dx: to.x - drag.from.x, dy: to.y - drag.from.y });
      told.current.onDrag(drag.by);
    }
    function up(event: PointerEvent): void {
      if (drag === null || event.pointerId !== drag.pointerId) {
        return;
      }
      const { by } = drag;
      drag = null;
      told.current.onDrop(by);
    }
    function cancel(): void {
      if (drag !== null) {
        drag = null;
        told.current.onDrag(null);
      }
    }
    function cancelled(event: KeyboardEvent): void {
      if (event.key === "Escape" && drag !== null) {
        // Only the drag: moving goes on.
        event.preventDefault();
        cancel();
      }
    }
    // The view's controls capture the pointer as a drag starts, so that its
    // moves and its end reach the view wherever they are.
    element.addEventListener("pointerdown", down);
    element.addEventListener("pointermove", move);
    element.addEventListener("pointerup", up);
    element.addEventListener("pointercancel", cancel);
    window.addEventListener("keydown", cancelled, true);
    return () => {
      element.removeEventListener("pointerdown", down);
      element.removeEventListener("pointermove", move);
      element.removeEventListener("pointerup", up);
      element.removeEventListener("pointercancel", cancel);
      window.removeEventListener("keydown", cancelled, true);
    };
  }, [camera, gl, heightM]);

  return null;
}
