import { useEffect } from "react";

import { type ScenarioSource, withField } from "../scene/edits";
import type { SetSource } from "../scene/useSource";
import { loadFieldNames } from "./FieldControls";
import { CLIMATE_FIELD } from "./source";

/**
 * A link to follow a run, and a replay's source, ask for the climate without
 * asking first which fields the scenario has, and a house built with no
 * equipment has no climate field: each of its moments would be refused and
 * said not to be drawn. Such a view draws no field, as the viewer's own way to
 * follow a run chooses (`SourceChooser`). A field chosen in the view, or named
 * in an address to look at, stays what it is asked to be, and says if it fails.
 * Fields that cannot be listed say nothing of the climate, which stays.
 */
export function useAbsentClimate({
  source,
  replayed,
  onSource,
}: {
  source: ScenarioSource;
  replayed: boolean;
  onSource: (change: SetSource) => void;
}): void {
  const { scenarioId, layout } = source;
  const unasked = source.field === CLIMATE_FIELD && (source.follow === true || replayed);
  useEffect(() => {
    if (!unasked) {
      return;
    }
    let current = true;
    void loadFieldNames(scenarioId, layout).then(({ names }) => {
      if (current && names.length > 0 && !names.includes(CLIMATE_FIELD)) {
        onSource((now) =>
          now.kind === "scenario" && now.scenarioId === scenarioId && now.field === CLIMATE_FIELD
            ? withField(now, null)
            : now,
        );
      }
    });
    return () => {
      current = false;
    };
  }, [unasked, scenarioId, layout, onSource]);
}
