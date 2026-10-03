import type { ReactElement } from "react";

import type { SceneEntity, SceneEntityKind } from "./generated/snapshotTypes";
import { ShapeMesh } from "./ShapeMesh";

/** How each kind of entity is drawn. Typed by the kinds the simulator
 * publishes, so a new kind does not compile until the viewer can draw it. */
export const RENDERERS: Record<SceneEntityKind, (entity: SceneEntity) => ReactElement> = {
  // The ground lies at the grid's depth; the grid's lines stay visible on it.
  GROUND: (entity) => <ShapeMesh shape={entity.shape} color={entity.color} behindLines />,
  AXES: (entity) => <ShapeMesh shape={entity.shape} color={entity.color} />,
  PLANT: (entity) => <ShapeMesh shape={entity.shape} color={entity.color} />,
};
