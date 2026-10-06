import type { ReactElement } from "react";
import type { Color, SceneEntity, SceneEntityKind } from "./generated/snapshotTypes";
import { isMetal } from "./materials";
import { SeeThrough } from "./SeeThrough";
import { ShapeMesh } from "./ShapeMesh";

/** How the viewer wants an entity to look: its colour, which a colouring may
 * replace, whether it is selected, and whether see-through parts should be
 * denser, so that a debug colouring reads on them. */
export interface EntityLook {
  color: Color;
  selected: boolean;
  emphasised: boolean;
}

function seeThrough(entity: SceneEntity, look: EntityLook, outlineOnly = false): ReactElement {
  const { shape } = entity;
  return shape.shape === "box" || shape.shape === "plane" || shape.shape === "polygon" ? (
    <SeeThrough
      shape={shape}
      color={look.color}
      highlighted={look.selected}
      outlineOnly={outlineOnly}
      dense={look.emphasised}
    />
  ) : (
    <ShapeMesh shape={shape} color={look.color} highlighted={look.selected} />
  );
}

/** A solid, drawn as metal if it is made of one. */
function solid(entity: SceneEntity, look: EntityLook): ReactElement {
  return (
    <ShapeMesh
      shape={entity.shape}
      color={look.color}
      highlighted={look.selected}
      metallic={isMetal(entity)}
    />
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
  // Glazing: see-through and framed by its edges. A click picks it only where
  // nothing solid lies behind it.
  WALL: (entity, look) => seeThrough(entity, look),
  ROOF: (entity, look) => seeThrough(entity, look),
  GUTTER: solid,
  // A vent is a glazed panel, framed; a door a solid one, seen from either side.
  VENT: (entity, look) => seeThrough(entity, look),
  DOOR: (entity, look) => (
    <ShapeMesh shape={entity.shape} color={look.color} highlighted={look.selected} doubleSided />
  ),
  // Posts and rafters are cylinders, so they are drawn in an instanced batch;
  // this draws one on its own, when it is selected. So are pipes and rails.
  FRAME: solid,
  // A disc on the floor where a plant can stand; batched, as cylinders are.
  PLANTING_POSITION: solid,
  // The layout's fixtures, each in its material.
  CROP_GUTTER: solid,
  BENCH: solid,
  SLAB: solid,
  WALKWAY: solid,
  // The volumes zones keep: see-through, picked only where nothing solid lies
  // behind, as glazing is.
  SERVICE_ZONE: (entity, look) => seeThrough(entity, look),
  KEEP_OUT: (entity, look) => seeThrough(entity, look),
  RAIL: solid,
  PIPE: solid,
  WIRE: solid,
  OBSTACLE: solid,
  PLANT: (entity, look) => (
    <ShapeMesh shape={entity.shape} color={look.color} highlighted={look.selected} />
  ),
};
