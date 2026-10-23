import type { ScenarioRun } from "../scene/run";
import { useLoad } from "../useLoad";
import { loadRunManifest, loadServedVersion, runManifestUrl, VERSION_URL } from "./manifest";
import { loadRunState, runStateUrl } from "./state";

/**
 * In QA mode only: the simulator's version and commit, as it says itself;
 * what the scenario's run drawn is made from; and what each process of the
 * run holds at its moment, the last on show until the next arrives.
 */
export function useQaLoads(qaMode: boolean, run: ScenarioRun | null) {
  const served = useLoad(qaMode ? VERSION_URL : null, loadServedVersion);
  const runManifest = useLoad(
    !qaMode || run === null ? null : runManifestUrl(run.scenarioId, run),
    loadRunManifest,
  );
  const runState = useLoad(
    !qaMode || run === null ? null : runStateUrl(run.scenarioId, run),
    loadRunState,
    { group: run === null ? "" : `state ${run.scenarioId}` },
  );
  return { served, runManifest, runState };
}
