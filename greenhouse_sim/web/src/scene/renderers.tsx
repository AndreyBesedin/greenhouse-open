import type { ReactElement } from "react";
import type { Color, SceneEntity, SceneEntityKind } from "./generated/snapshotTypes";
import { SeeThrough } from "./SeeThrough";
import { ShapeMesh } from "./ShapeMesh";

/** How the viewer wants an entity to look: its colour, which a colouring may
 * replace, and whether it is selected. */
export interface EntityLook {
  color: Color;
  selected: boolean;
}

function seeThrough(entity: SceneEntity, look: EntityLook, outlineOnly = false): ReactElement {
  const { shape } = entity;
  return shape.shape === "box" || shape.shape === "plane" ? (
    <SeeThrough
      shape={shape}
      color={look.color}
      highlighted={look.selected}
      outlineOnly={outlineOnly}
    />
  ) : (
    <ShapeMesh shape={shape} color={look.color} highlighted={look.selected} />
  );
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
  // A space rather than a solid, lying on the greenhouse's walls: an outline
  // that takes no clicks, so the walls and floor take them.
  GREENHOUSE_BOUNDS: (entity, look) => seeThrough(entity, look, true),
  // The floor lies at the grid's depth, as the ground does.
  FLOOR: (entity, look) => (
    <ShapeMesh shape={entity.shape} color={look.color} highlighted={look.selected} behindLines />
  ),
  // Glazing: see-through, framed by its edges, and clickable by them.
  WALL: (entity, look) => seeThrough(entity, look),
  PLANT: (entity, look) => (
    <ShapeMesh shape={entity.shape} color={look.color} highlighted={look.selected} />
  ),
};
