import { DAY_S } from "./clock";
import { SCENARIO_SUMMARY_SCHEMA } from "./generated/scenarioSummarySchema";
import type { ScenarioSummary as ServedSummary } from "./generated/scenarioSummaryTypes";
import { contractCheck, loadJson } from "./loadJson";
import type { ScheduledCommand } from "./scene/source";

// A day's noon, as a share of it.
const HALF_DAY = 0.5;

/** A scenario as the simulator's local API lists it (`GET /api/scenarios`). */
export interface ScenarioSummary {
  id: string;
  name: string;
  description: string;
  plants: number;
  duration_days: number;
  /** How its runs grow its crop: organ by organ (`ORGAN_CROP`), or by the
   * simple daily model. */
  crop_model?: string;
  /** The commands its runs give at a time of day, every day, unless a run
   * gives its own. */
  daily?: { time_of_day_s: number; actuator_id: string; level: number }[];
  /** Its doors' and vents' identifiers, which commands open as they do its
   * equipment. */
  openings?: string[];
  /** The day of its run where the viewer opens it, kept as a checkpoint, if
   * its manifest names one. */
  opening_day?: number | null;
  /** The names of its layouts, its default first. */
  layouts: string[];
  /** The names of the weathers it can be run under, its own first. */
  weathers?: string[];
  /** The heater a thermostat runs by the house's air, if it has one. */
  thermostat?: string | null;
}

/** The layout a scenario is defined with. */
export const DEFAULT_LAYOUT = "default";
/** The name of a scenario's own weather, beside the presets'. */
export const DEFAULT_WEATHER = "default";

export type ScenariosState =
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; scenarios: ScenarioSummary[] };

const checkSummary = contractCheck<ServedSummary>(SCENARIO_SUMMARY_SCHEMA, "the scenario");

/** The scenarios in a response body, checked rather than trusted. */
export function parseScenarios(body: unknown): ScenarioSummary[] {
  if (!Array.isArray(body)) {
    throw new Error("expected a list of scenarios");
  }
  return body.map((item: unknown, index) => {
    const checked = checkSummary(item);
    if (!checked.ok) {
      throw new Error(`scenario ${index} is not a scenario summary`);
    }
    return checked.value;
  });
}

/** Where the viewer opens a scenario shown from the list: its climate at
 * noon on its opening day (P09.5), if it has one; at its start, if not. */
export function openingMoment(
  summary: ScenarioSummary | undefined,
): { field: string; time: number } | null {
  const day = summary?.opening_day;
  return day === undefined || day === null
    ? null
    : { field: "climate", time: (day + HALF_DAY) * DAY_S };
}

/** A scenario's own daily commands, as the viewer writes commands. */
export function ownDaily(summary: ScenarioSummary | undefined): ScheduledCommand[] {
  return (summary?.daily ?? []).map(({ time_of_day_s, actuator_id, level }) => ({
    timeS: time_of_day_s,
    actuatorId: actuator_id,
    level,
  }));
}

/** Asks the simulator for its scenarios; any failure becomes `unavailable`. */
export const SCENARIOS_URL = "/api/scenarios";

export async function loadScenarios(fetchFn: typeof fetch = fetch): Promise<ScenariosState> {
  const answer = await loadJson(SCENARIOS_URL, parseScenarios, fetchFn);
  return answer.status === "loaded" ? { status: "loaded", scenarios: answer.value } : answer;
}
