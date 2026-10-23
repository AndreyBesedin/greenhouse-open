import { daysEnded } from "../clock";
import { cropUrl, ORGAN_CROP } from "../plants/crop";
import type { ScenarioSummary } from "../scenarios";
import { useLoad, useLoadProgress } from "../useLoad";
import { equipmentUrl, governedLevels, loadEquipment } from "./equipment";
import type { ScenarioRun } from "./run";
import { fetchScene, loadScene, sceneRequest } from "./sceneLoad";
import type { SceneSource } from "./source";

const NO_OPENINGS: readonly string[] = [];

/**
 * What a view draws of its scene: the scene, its crop and, for a scenario
 * whose thermostat runs its heater, the equipment as the run has it.
 *
 * A thermostat runs its heater by the house's air (P10.3), which only the
 * run knows: the scene draws the heater as the run has it at the moment. A
 * scenario reopened by its sliders, or the plant lab on another day, keeps
 * its scene on show until the next arrives; any other change of scene starts
 * from loading. A crop grown organ by organ is drawn as it stands at the
 * moment, in place of its transplants once a day has ended; the last stays
 * on show until the next day's arrives, and when the next day's fails.
 */
export function useSceneLoads(
  source: SceneSource,
  summary: ScenarioSummary | undefined,
  run: ScenarioRun | null,
) {
  const openingIds = summary?.openings ?? NO_OPENINGS;
  const equipment = useLoad(
    run !== null && summary?.thermostat ? equipmentUrl(run.scenarioId, run) : null,
    loadEquipment,
  );
  const governed = governedLevels(equipment);
  const sceneAsked = sceneRequest(source, openingIds, governed);
  const sceneProgress = useLoadProgress(
    sceneAsked,
    (_url, fetchFn) => loadScene(source, fetchFn, openingIds, governed),
    {
      group:
        source.kind === "scenario"
          ? `scenario ${source.scenarioId}`
          : source.kind === "plants"
            ? "plants"
            : (sceneAsked ?? ""),
    },
  );
  const organCrop = summary?.crop_model === ORGAN_CROP;
  const cropProgress = useLoadProgress(
    run === null || !organCrop || daysEnded(run.time ?? 0) === 0 ? null : cropUrl(run),
    fetchScene,
    { group: run === null ? "" : `crop ${run.scenarioId}` },
  );
  return { equipment, sceneProgress, cropProgress, organCrop };
}
