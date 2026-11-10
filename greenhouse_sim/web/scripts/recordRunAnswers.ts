// Records what a replay's panels ask the simulator about a run of the reference
// greenhouse, at one moment, into `e2e/visual/runAnswers.json.gz`: the answers the
// visual checks give the run's panels, which they draw with no simulator
// (`e2e/visual/pageAnswers.ts`). Written again when a contract it holds changes,
// with the simulator serving its API (`uv run api`), from `greenhouse_sim/web`:
//
//     node scripts/recordRunAnswers.ts
//
// The viewer checks each answer against its contract as it reads it, so that a
// stale one shows as a refusal in the baselines rather than passing unseen.
import { writeFileSync } from "node:fs";
import { gzipSync } from "node:zlib";

import { DEFAULT_SIMULATOR_API_PORT, simulatorApi } from "../simulatorApi.ts";

/** The scenario, seed and moment recorded: day 2 at noon, its fans on and its
 * vents open, by its daily schedule. */
export const RECORDED = { scenarioId: "reference_greenhouse", seed: 7, timeS: 129_600 } as const;
const DAY_S = 86_400;
const HOUR_S = 3600;
// Numbers are rounded, so that a recording is not larger than what it shows.
const DIGITS = 6;

const api = simulatorApi(Number(process.env.SIMULATOR_API_PORT ?? DEFAULT_SIMULATOR_API_PORT));
const scenario = `/api/scenarios/${RECORDED.scenarioId}`;

async function asked(path: string, query: Record<string, string> = {}): Promise<unknown> {
  const search = new URLSearchParams(query).toString();
  const response = await fetch(`${api}${path}${search === "" ? "" : `?${search}`}`);
  if (!response.ok) {
    throw new Error(`${path}: ${response.status} ${await response.text()}`);
  }
  return response.json();
}

function rounded(value: unknown): unknown {
  if (typeof value === "number") {
    return Number(value.toFixed(DIGITS));
  }
  if (Array.isArray(value)) {
    return value.map(rounded);
  }
  if (value !== null && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, rounded(item)]));
  }
  return value;
}

interface Entity {
  properties: Record<string, unknown>;
}

/** A snapshot without its plants' organs, which only the scene draws: the panels
 * read the house, its equipment, openings and sensors. */
function withoutOrgans(snapshot: { entities: Entity[] }): unknown {
  return {
    ...snapshot,
    entities: snapshot.entities.filter((entity) => !("organ_id" in entity.properties)),
  };
}

const summaries = (await asked("/api/scenarios")) as { id: string; daily: Daily[] }[];
interface Daily {
  time_of_day_s: number;
  actuator_id: string;
  level: number;
}
const summary = summaries.find((each) => each.id === RECORDED.scenarioId);
if (summary === undefined) {
  throw new Error(`the simulator lists no ${RECORDED.scenarioId}`);
}
const run = {
  daily: summary.daily.map((at) => `${at.time_of_day_s}:${at.actuator_id}:${at.level}`).join(","),
  weather: `default#${RECORDED.seed}`,
};
const at = { ...run, t: String(RECORDED.timeS) };
const equipment = (await asked(`${scenario}/climate/equipment`, at)) as {
  levels: Record<string, number>;
};
// The openings as the daily schedule has set them by then: what is not a device.
const timeOfDay = RECORDED.timeS % DAY_S;
const opened: Record<string, number> = {};
for (const each of summary.daily) {
  if (!(each.actuator_id in equipment.levels) && each.time_of_day_s <= timeOfDay) {
    opened[each.actuator_id] = each.level;
  }
}
const levels = (shown: Record<string, number>) =>
  Object.entries(shown)
    .map(([id, level]) => `${id}:${level}`)
    .join(",");

// By path; the house's air both with and without its run all off beside it.
const answers: Record<string, unknown> = {
  "/api/scenarios": [summary],
  [`${scenario}/fields`]: await asked(`${scenario}/fields`),
  [`${scenario}/weather`]: await asked(`${scenario}/weather`, at),
  [`${scenario}/weather/day`]: await asked(`${scenario}/weather/day`, {
    ...at,
    t: String(Math.ceil(RECORDED.timeS / DAY_S) * DAY_S),
  }),
  [`${scenario}/scene`]: withoutOrgans(
    (await asked(`${scenario}/scene`, {
      open: levels(opened),
      set: levels(equipment.levels),
    })) as { entities: Entity[] },
  ),
  [`${scenario}/crop`]: withoutOrgans(
    (await asked(`${scenario}/crop`, {
      ...at,
      t: String(Math.floor(RECORDED.timeS / DAY_S) * DAY_S),
    })) as { entities: Entity[] },
  ),
  [`${scenario}/climate/equipment`]: equipment,
  [`${scenario}/climate/openings`]: await asked(`${scenario}/climate/openings`, at),
  [`${scenario}/climate/glazing`]: await asked(`${scenario}/climate/glazing`, at),
  [`${scenario}/climate/house`]: await asked(`${scenario}/climate/house`, at),
  [`${scenario}/climate/house?all_off=0`]: await asked(`${scenario}/climate/house`, {
    ...at,
    all_off: "0",
  }),
  [`${scenario}/fields/climate`]: await asked(`${scenario}/fields/climate`, at),
  [`${scenario}/timeline`]: await asked(`${scenario}/timeline`, {
    daily: run.daily,
    // The hour the moment ends, the timeline's first window.
    from: String(RECORDED.timeS - HOUR_S),
    t: at.t,
  }),
};

const file = new URL("../e2e/visual/runAnswers.json.gz", import.meta.url);
writeFileSync(file, gzipSync(JSON.stringify({ recorded: RECORDED, answers: rounded(answers) })));
console.log(`wrote ${file.pathname}`);
