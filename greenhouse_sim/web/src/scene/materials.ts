import type { Material, SceneEntity } from "./generated/snapshotTypes";

// Materials drawn as metal: somewhat shiny, as `METAL` describes.
const METALS: ReadonlySet<Material> = new Set(["steel", "aluminium"]);

/** Whether an entity is drawn as metal: it is made of a metal. */
export function isMetal(entity: SceneEntity): boolean {
  return entity.material !== null && METALS.has(entity.material);
}
