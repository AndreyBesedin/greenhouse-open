import type { ScenarioRun } from "../scene/run";
import { useLoad, useLoadProgress } from "../useLoad";
import type { Point3 } from "../world";
import { glazingUrl, loadGlazing } from "./glazing";
import { houseAirOnShow, houseAirUrl, loadHouseAir, ownHouseAirUrl, withAllOff } from "./HouseAir";
import { loadOpenings, openingsUrl } from "./openingFlows";
import { loadProbeCharts, probeChartsUrl } from "./ProbeCharts";

/**
 * What a climate run drawn (`climate`, null without one) holds besides its
 * field: what the probes read through it, and through the same run all off,
 * up to the moment drawn; the house's air as one volume, likewise, the run's
 * own apart from the same run all off, for which it does not wait; the
 * glazing at the moment drawn, each wall's and roof slope's temperature, for
 * "Colour by"; and what the open doors and vents pass, for "Colour by" and
 * their arrows.
 */
export function useClimateLoads(climate: ScenarioRun | null, probes: readonly Point3[]) {
  const probeCharts = useLoad(
    climate === null || probes.length === 0
      ? null
      : probeChartsUrl(climate.scenarioId, { ...climate, probes }),
    loadProbeCharts,
  );
  const ownHouseAir = houseAirOnShow(
    useLoadProgress(
      climate === null ? null : ownHouseAirUrl(climate.scenarioId, climate),
      loadHouseAir,
    ),
  );
  const wholeHouseAir = useLoadProgress(
    climate === null ? null : houseAirUrl(climate.scenarioId, climate),
    loadHouseAir,
  );
  const houseAir = withAllOff(ownHouseAir, wholeHouseAir.shown);
  const glazing = useLoad(
    climate === null ? null : glazingUrl(climate.scenarioId, climate),
    loadGlazing,
  );
  const openingFlows = useLoad(
    climate === null ? null : openingsUrl(climate.scenarioId, climate),
    loadOpenings,
  );
  return { probeCharts, houseAir, glazing, openingFlows };
}
