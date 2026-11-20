import { type Answered, refusal } from "../builder/api";
import type { SetKey } from "../builder/parameterSetLibrary";
import { SCENARIO_SUMMARY_SCHEMA } from "../generated/scenarioSummarySchema";
import type { ScenarioSummary } from "../generated/scenarioSummaryTypes";
import { contractReader } from "../loadJson";
import { DEFAULT_WEATHER } from "../scenarios";
import { parseStoredRun, type StoredRun } from "./storedRuns";

/** The pace a run is started at unless another is asked for, in real seconds
 * for a simulated day, as a person enters it. */
export const DEFAULT_PACE_S = "10";

/** What a run is asked for at, as a person enters it: its seed, or none for the
 * scenario's own; how many real seconds a simulated day takes, or none for as
 * fast as it can be computed; and, if given, its weather by name and its days,
 * or the scenario's own (decision 0075); and the parameter set its crop grows,
 * if another than its scenario's (P20.5). */
export interface RunAsked {
  seed: string;
  secondsPerDay: string;
  weather?: string;
  days?: string;
  parameterSet?: SetKey;
}

const readScenario = contractReader<ScenarioSummary>(
  SCENARIO_SUMMARY_SCHEMA,
  "the simulator's answer is not a scenario",
);

/** The scenario of a house under another of its crop model's parameter sets,
 * which the simulator registers as a scenario of its own: its identifier, or
 * why it was refused, such as for a packaged scenario. */
async function underSet(
  scenarioId: string,
  { name, version }: SetKey,
  fetchFn: typeof fetch,
): Promise<Answered<string>> {
  const url = `/api/scenarios/${encodeURIComponent(scenarioId)}/under/${encodeURIComponent(name)}/${version}`;
  const response = await fetchFn(url, { method: "POST" });
  if (!response.ok) {
    return { ok: false, problem: await refusal(response) };
  }
  return { ok: true, value: readScenario(await response.json()).id };
}

/** A run of a scenario given to a worker, beside any others of it (decision
 * 0065): the epoch it is, queued, or why it was refused. Under another
 * parameter set, it is a run of the scenario the simulator registers for the
 * house under that set, which the epoch's `scenario_id` names. */
export async function startRun(
  scenarioId: string,
  { seed, secondsPerDay, weather = DEFAULT_WEATHER, days = "", parameterSet }: RunAsked,
  fetchFn: typeof fetch = fetch,
): Promise<Answered<StoredRun>> {
  const query = new URLSearchParams();
  if (seed !== "") {
    query.set("seed", seed);
  }
  if (secondsPerDay !== "") {
    query.set("seconds_per_day", secondsPerDay);
  }
  if (weather !== DEFAULT_WEATHER) {
    query.set("weather", weather);
  }
  if (days !== "") {
    query.set("duration_days", days);
  }
  try {
    let runOf = scenarioId;
    if (parameterSet !== undefined) {
      const under = await underSet(scenarioId, parameterSet, fetchFn);
      if (!under.ok) {
        return under;
      }
      runOf = under.value;
    }
    const url = `/api/scenarios/${encodeURIComponent(runOf)}/runs?${query}`;
    const response = await fetchFn(url, { method: "POST" });
    if (!response.ok) {
      return { ok: false, problem: await refusal(response) };
    }
    const run = parseStoredRun(await response.json());
    return run === null
      ? { ok: false, problem: "the simulator's answer is not a run" }
      : { ok: true, value: run };
  } catch (error) {
    return { ok: false, problem: error instanceof Error ? error.message : String(error) };
  }
}
