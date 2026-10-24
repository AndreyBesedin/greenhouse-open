import { type ComponentProps, memo, useMemo } from "react";

import { categoryColor } from "../debug/categories";
import { type Colouring, scalarColor, scalarValue } from "../debug/scalar";
import { highlighted } from "../selection";
import type { Color, SceneEntity, SceneSnapshot } from "./generated/snapshotTypes";
import { InstancedShapes } from "./InstancedShapes";
import { isInstanced, shapeBatches } from "./instancing";
import type { Offset } from "./moves";
import { placement } from "./placement";
import { RENDERERS } from "./renderers";

/** The colour an entity is drawn in: its category's in the categories' debug
 * view, a colouring's where it has the property, or its own. */
function shownColor(entity: SceneEntity, colouring: Colouring | null, byCategory: boolean): Color {
  const category = byCategory ? categoryColor(entity.kind) : null;
  if (category !== null) {
    return category;
  }
  const value = colouring === null ? null : scalarValue(entity, colouring.property);
  return colouring === null || value === null ? entity.color : scalarColor(value, colouring.range);
}

/**
 * A checked snapshot. Belongs inside the world's z-up group. Cylinders,
 * spheres and ellipsoids, the shapes repeated by the hundred in a greenhouse
 * (posts, rafters, pipes, and plants' stems, leaflets and fruits), are drawn
 * in one instanced batch per kind, per shape and per finish: metal or not.
 * Every other entity, and a highlighted one, which glows, is drawn on its own
 * by its kind's renderer: the selected entity and, if it is part of a plant's
 * organ, the organ's other parts. Either way a click can tell which entity it
 * landed on (`pickEntity`): an entity's own group carries its identifier, and
 * a batch lists its entities.
 */
function SceneDrawn({
  snapshot,
  selectedId = null,
  colouring = null,
  showBounds = false,
  byCategory = false,
  nudged = null,
}: {
  snapshot: SceneSnapshot;
  selectedId?: string | null;
  /** Shades the entities that have the property; the others keep their colour. */
  colouring?: Colouring | null;
  /** The greenhouse's bounds are a debug aid: they lie on its walls, and are
   * drawn only when asked for. */
  showBounds?: boolean;
  /** Colours each part of the envelope by its semantic category. */
  byCategory?: boolean;
  /** Entities drawn moved along the floor, by identifier, as a Move session
   * places them and a drag takes them (#209, #271): each drawn on its own. */
  nudged?: Readonly<Record<string, Offset>> | null;
}) {
  // Which entities are drawn moved, apart from how far, so that a drag
  // does not batch the scene's shapes again at every step.
  const moved = Object.keys(nudged ?? {})
    .sort()
    .join("\n");
  const { batches, single, glowing } = useMemo(() => {
    const glowing = highlighted(snapshot, selectedId);
    const alone = new Set(moved === "" ? [] : moved.split("\n"));
    return {
      glowing,
      batches: shapeBatches(snapshot.entities).map(({ batch, shape, metallic, entities: all }) => {
        const batched = all.filter(
          (entity) => !glowing.has(entity.entity_id) && !alone.has(entity.entity_id),
        );
        return {
          batch,
          shape,
          metallic,
          entities: batched,
          colors: batched.map((entity) => shownColor(entity, colouring, byCategory)),
          capacity: all.length,
        };
      }),
      single: snapshot.entities.filter(
        (entity) =>
          (!isInstanced(entity) || glowing.has(entity.entity_id) || alone.has(entity.entity_id)) &&
          (showBounds || entity.kind !== "GREENHOUSE_BOUNDS"),
      ),
    };
  }, [snapshot, selectedId, colouring, showBounds, byCategory, moved]);

  return (
    <>
      {batches.map(({ batch, shape, metallic, entities, colors, capacity }) => (
        <InstancedShapes
          key={`${batch}-${capacity}`}
          shape={shape}
          entities={entities}
          colors={colors}
          capacity={capacity}
          metallic={metallic}
        />
      ))}
      {single.map((entity) => {
        const { position, quaternion } = placement(entity.transform);
        const by = nudged?.[entity.entity_id] ?? null;
        const look = {
          color: shownColor(entity, colouring, byCategory),
          selected: glowing.has(entity.entity_id),
          emphasised: byCategory,
        };
        return (
          <group
            key={entity.entity_id}
            position={
              by === null ? position : [position[0] + by.dx, position[1] + by.dy, position[2]]
            }
            quaternion={quaternion}
            userData={{ entityId: entity.entity_id, entityKind: entity.kind }}
          >
            {RENDERERS[entity.kind](entity, look)}
          </group>
        );
      })}
    </>
  );
}

/** Whether two sets of moves draw the same: the same entities, each moved as far. */
function sameMoves(
  a: Readonly<Record<string, Offset>> | null | undefined,
  b: Readonly<Record<string, Offset>> | null | undefined,
): boolean {
  const these = Object.entries(a ?? {});
  return (
    these.length === Object.keys(b ?? {}).length &&
    these.every(([id, by]) => {
      const other = b?.[id];
      return other !== undefined && other.dx === by.dx && other.dy === by.dy;
    })
  );
}

/**
 * The scene, drawn again only when what it draws changes. Each entity it
 * draws on its own takes a new colour and identifier object as it renders,
 * and a changed prop draws a frame (decision 0053): re-rendered with the page
 * for the HUD's report, the scene drew again, and the HUD reported again.
 * Its moves are compared by value, as the page makes them anew each render.
 */
export const SceneView = memo(
  SceneDrawn,
  (before: ComponentProps<typeof SceneDrawn>, after: ComponentProps<typeof SceneDrawn>) =>
    before.snapshot === after.snapshot &&
    before.selectedId === after.selectedId &&
    before.colouring === after.colouring &&
    before.showBounds === after.showBounds &&
    before.byCategory === after.byCategory &&
    sameMoves(before.nudged, after.nudged),
);
