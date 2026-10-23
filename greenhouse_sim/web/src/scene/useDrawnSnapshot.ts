import { useMemo } from "react";

import type { GlazingState } from "../fields/glazing";
import { withGlazing } from "../fields/glazing";
import { type OpeningsState, withOpeningFlows } from "../fields/openingFlows";
import { withCrop } from "../plants/crop";
import type { Pending } from "../useLoad";
import type { SceneSnapshot } from "./generated/snapshotTypes";

/** The scene drawn: the one shown, its crop as it stands at the moment drawn
 * (`grown`), its glazed surfaces carrying their temperatures and its open
 * doors and vents their flows, while a climate run is drawn. */
export function useDrawnSnapshot(
  shown: SceneSnapshot | null,
  grown: SceneSnapshot | null,
  glazing: GlazingState | Pending,
  openingFlows: OpeningsState | Pending,
): SceneSnapshot | null {
  return useMemo(() => {
    if (shown === null) {
      return null;
    }
    const cropped = grown === null ? shown : withCrop(shown, grown);
    const glazed = glazing.status === "loaded" ? withGlazing(cropped, glazing.glazing) : cropped;
    return openingFlows.status === "loaded"
      ? withOpeningFlows(glazed, openingFlows.openings)
      : glazed;
  }, [shown, grown, glazing, openingFlows]);
}
