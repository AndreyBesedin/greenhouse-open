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
 * of another seed is drawn with its weather and its crop's walk; and under the
 * plan the changes given to it make (P17.8), each shown from its moment.
 */
export function replaySource(
  position: Pick<
    PositionState,
    "scenario_id" | "layout" | "seed" | "targets" | "commands" | "crop"
  >,
): SceneSource {
  const { targets, commands, crop } = position;
  return {
    kind: "scenario",
    scenarioId: position.scenario_id,
    ...(position.layout === DEFAULT_LAYOUT ? {} : { layout: position.layout }),
    ...(position.seed === null
      ? {}
      : { weather: `${DEFAULT_WEATHER}${SEED_MARK}${position.seed}` }),
    field: CLIMATE_FIELD,
    ...(targets.length === 0
      ? {}
      : { targets: targets.map(([timeS, target, valueC]) => ({ timeS, target, valueC })) }),
    ...(commands.length === 0
      ? {}
      : { schedule: commands.map(([timeS, actuatorId, level]) => ({ timeS, actuatorId, level })) }),
    ...(crop.length === 0
      ? {}
      : { crop: crop.map(([timeS, plantId, kind, target]) => ({ timeS, plantId, kind, target })) }),
  };
}

/** What identifies the plan of a replay's scene: a running epoch's grows. */
export function planKey(position: Pick<PositionState, "targets" | "commands" | "crop">): string {
  return JSON.stringify([position.targets, position.commands, position.crop]);
}

/** The scene shown, under the plan of the epoch replayed, the rest of what the
 * viewer has chosen kept: the same scene, if its plan is the same. */
export function withPlanOf(shown: SceneSource, replayed: SceneSource): SceneSource {
  if (shown.kind !== "scenario" || replayed.kind !== "scenario") {
    return shown;
  }
  const same = (a: unknown, b: unknown) => JSON.stringify(a ?? []) === JSON.stringify(b ?? []);
  if (
    same(shown.targets, replayed.targets) &&
    same(shown.schedule, replayed.schedule) &&
    same(shown.crop, replayed.crop)
  ) {
    return shown;
  }
  const { targets: _targets, schedule: _schedule, crop: _crop, ...rest } = shown;
  return {
    ...rest,
    ...(replayed.targets === undefined ? {} : { targets: replayed.targets }),
    ...(replayed.schedule === undefined ? {} : { schedule: replayed.schedule }),
    ...(replayed.crop === undefined ? {} : { crop: replayed.crop }),
  };
}
