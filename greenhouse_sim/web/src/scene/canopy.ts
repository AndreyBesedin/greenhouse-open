import type { SceneEntity } from "./generated/snapshotTypes";

// A canopy is never drawn quite clear, so that an empty one still shows its
// row, nor solid, so that the row shows through the densest (decision 0062).
export const CANOPY_CLEAREST = 0.06;
export const CANOPY_DENSEST = 0.55;

/** How opaque a crop grown by area's canopy is drawn: from its clearest to
 * its densest as its density, the share of the light its leaves take, goes
 * from 0 to 1. A density out of range is taken at its nearest bound, and one
 * missing or not a number at its clearest. */
export function canopyOpacity(entity: SceneEntity): number {
  const { density } = entity.properties;
  const share =
    typeof density === "number" && Number.isFinite(density) ? Math.min(1, Math.max(0, density)) : 0;
  return CANOPY_CLEAREST + (CANOPY_DENSEST - CANOPY_CLEAREST) * share;
}
