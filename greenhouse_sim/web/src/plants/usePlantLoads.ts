import type { ScenarioRun } from "../scene/run";
import { useLoad } from "../useLoad";
import { cropPlantUrl, loadCropPlant } from "./crop";
import { loadPlantsLight, plantsLightUrl } from "./light";

/**
 * What a view reads of its plants: the light on them at the moment drawn,
 * while a plant is selected in a climate run's view (`climate`), or in QA
 * mode, which labels every plant with it, the last on show until the next
 * arrives; and the plant selected in a crop grown organ by organ
 * (`organCrop`), as it stands at the moment drawn, with each day it lived.
 */
export function usePlantLoads({
  run,
  climate,
  organCrop,
  selectedPlant,
  qaMode,
}: {
  run: ScenarioRun | null;
  climate: ScenarioRun | null;
  organCrop: boolean;
  selectedPlant: string | null;
  qaMode: boolean;
}) {
  const plantsLight = useLoad(
    climate === null || (selectedPlant === null && !qaMode)
      ? null
      : plantsLightUrl(climate.scenarioId, climate),
    loadPlantsLight,
  );
  const cropPlant = useLoad(
    run === null || !organCrop || selectedPlant === null ? null : cropPlantUrl(run, selectedPlant),
    loadCropPlant,
  );
  return { plantsLight, cropPlant };
}
