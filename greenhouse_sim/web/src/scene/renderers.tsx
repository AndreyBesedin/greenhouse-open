import type { ReactElement } from "react";
import { BoundsBox } from "./BoundsBox";
import type { Color, SceneEntity, SceneEntityKind } from "./generated/snapshotTypes";
import { ShapeMesh } from "./ShapeMesh";

/** How the viewer wants an entity to look: its colour, which a colouring may
 * replace, and whether it is selected. */
export interface EntityLook {
  color: Color;
  selected: boolean;
}

/** How each kind of entity is drawn. Typed by the kinds the simulator
 * publishes, so a new kind does not compile until the viewer can draw it. */
export const RENDERERS: Record<
  SceneEntityKind,
  (entity: SceneEntity, look: EntityLook) => ReactElement
> = {
  // The ground lies at the grid's depth; the grid's lines stay visible on it.
  GROUND: (entity, look) => (
    <ShapeMesh shape={entity.shape} color={look.color} highlighted={look.selected} behindLines />
  ),
  AXES: (entity, look) => (
    <ShapeMesh shape={entity.shape} color={look.color} highlighted={look.selected} />
  ),
  // A space rather than a solid: see-through, and clickable by its edges.
  GREENHOUSE_BOUNDS: (entity, look) =>
    entity.shape.shape === "box" ? (
      <BoundsBox shape={entity.shape} color={look.color} highlighted={look.selected} />
    ) : (
      <ShapeMesh shape={entity.shape} color={look.color} highlighted={look.selected} />
    ),
  PLANT: (entity, look) => (
    <ShapeMesh shape={entity.shape} color={look.color} highlighted={look.selected} />
  ),
};
