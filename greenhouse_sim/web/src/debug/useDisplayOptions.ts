import { useMemo, useState } from "react";

import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import { ALL_OVERLAYS, type OverlayToggles } from "./overlays";
import { colouringBy, scalarProperties } from "./scalar";

/**
 * How a view draws what it shows, as its display options choose: which
 * overlays are shown, the property its entities are coloured by, if any, and
 * the colouring that makes of `snapshot`, with the properties it could be
 * coloured by; whether the scene's dimensions are drawn; and whether its
 * entities are coloured by category.
 */
export function useDisplayOptions(snapshot: SceneSnapshot | null) {
  const [toggles, setToggles] = useState<OverlayToggles>(ALL_OVERLAYS);
  const [colourBy, setColourBy] = useState<string | null>(null);
  const [showDimensions, setShowDimensions] = useState(false);
  const [byCategory, setByCategory] = useState(false);
  const colourProperties = useMemo(
    () => (snapshot === null ? [] : scalarProperties(snapshot)),
    [snapshot],
  );
  const colouring = useMemo(
    () => (snapshot === null || colourBy === null ? null : colouringBy(snapshot, colourBy)),
    [snapshot, colourBy],
  );
  return {
    toggles,
    setToggles,
    colourBy,
    setColourBy,
    showDimensions,
    setShowDimensions,
    byCategory,
    setByCategory,
    colourProperties,
    colouring,
  };
}
