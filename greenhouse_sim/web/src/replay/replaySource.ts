import { CLIMATE_FIELD } from "../fields/source";
import { DEFAULT_LAYOUT, DEFAULT_WEATHER } from "../scenarios";
import type { SceneSource } from "../scene/source";
import type { PositionState } from "./position";

// A seed rides the weather's name, after this mark (`default#7`): the
// simulator reads `default` as the scenario's own weather.
const SEED_MARK = "#";

/**
 * The scene a replay draws, before any moment: the stored epoch's own run, its
 * scenario in its layout, under its seed (P17.6, decision 0065). The viewer
 * asks for the scene by the same parts the epoch was started with, so a run
 * of another seed is drawn with its weather and its crop's walk.
 */
export function replaySource(
  position: Pick<PositionState, "scenario_id" | "layout" | "seed">,
): SceneSource {
  return {
    kind: "scenario",
    scenarioId: position.scenario_id,
    ...(position.layout === DEFAULT_LAYOUT ? {} : { layout: position.layout }),
    ...(position.seed === null
      ? {}
      : { weather: `${DEFAULT_WEATHER}${SEED_MARK}${position.seed}` }),
    field: CLIMATE_FIELD,
  };
}
