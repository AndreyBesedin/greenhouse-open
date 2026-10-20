import { contractReader, loadJson } from "../loadJson";
import { DEFAULT_WEATHER } from "../scenarios";
import type { ScenarioSource } from "../scene/edits";
import { type RunParts, runParameters, scenarioUrl } from "../scene/run";
import type { ScheduledCommand } from "../scene/source";
import { CHECKPOINT_SCHEMA } from "./generated/checkpointSchema";
import type { Commanded, CheckpointSummary as ServedCheckpoint } from "./generated/checkpointTypes";

/** Where the API lists the checkpoints it keeps, and takes one uploaded. */
export const CHECKPOINTS_URL = "/api/checkpoints";
// How a weather's name says its clouds and its wind are overridden.
const CLOUDS_MARK = "@";
const WIND_MARK = "~";

/** A checkpoint as the API lists it (P09.5): a run's state at the start of
 * its day `day`, `timeS` into it, and the parts of the run it belongs to. */
export interface CheckpointSummary {
  checkpointId: string;
  scenarioId: string;
  layout: string;
  /** The weather's name as the API takes it, its overrides and all. */
  weather: string;
  levels: Record<string, number>;
  openings: Record<string, number>;
  /** The commands its run gave before its day. */
  commands: ScheduledCommand[];
  /** Its run's daily commands, or null for its scenario's own. */
  daily: ScheduledCommand[] | null;
  day: number;
  timeS: number;
  /** How many plants it keeps, organ by organ. */
  plants: number;
}

export type CheckpointsState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; checkpoints: CheckpointSummary[] };

/** What saving or uploading one answered: the checkpoint, or why not. */
export type CheckpointMade =
  | { ok: true; checkpoint: CheckpointSummary }
  | { ok: false; problem: string };

type Fields = Record<string, unknown>;

const readCheckpoint = contractReader<ServedCheckpoint>(
  CHECKPOINT_SCHEMA,
  "a checkpoint is not what the viewer expects",
);

function commandsFrom(commands: Commanded[]): ScheduledCommand[] {
  return commands.map(([timeS, actuatorId, level]) => ({ timeS, actuatorId, level }));
}

/** A checkpoint as the API lists it, checked rather than trusted. */
export function parseCheckpoint(body: unknown): CheckpointSummary {
  const checkpoint = readCheckpoint(body);
  return {
    checkpointId: checkpoint.checkpoint_id,
    scenarioId: checkpoint.scenario_id,
    layout: checkpoint.layout,
    weather: checkpoint.weather,
    levels: checkpoint.levels,
    openings: checkpoint.openings,
    commands: commandsFrom(checkpoint.commands),
    daily: checkpoint.daily === null ? null : commandsFrom(checkpoint.daily),
    day: checkpoint.day,
    timeS: checkpoint.time_s,
    plants: checkpoint.plants,
  };
}

async function refusal(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    const error = typeof body === "object" && body !== null ? (body as Fields).error : null;
    return typeof error === "string" ? error : `the simulator API answered ${response.status}`;
  } catch {
    return `the simulator API answered ${response.status}`;
  }
}

/** Fetches the checkpoints kept; every failure becomes `unavailable`. */
export async function loadCheckpoints(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<CheckpointsState> {
  const answer = await loadJson(url, checkpointsOf, fetchFn, refusal);
  return answer.status === "loaded" ? { status: "loaded", checkpoints: answer.value } : answer;
}

function checkpointsOf(body: unknown): CheckpointSummary[] {
  if (!Array.isArray(body)) {
    throw new Error("the checkpoints are not a list");
  }
  return body.map(parseCheckpoint);
}

/** Where a checkpoint of a scenario's run, asked for as the climate is, is
 * saved: at the start of the day its moment lies in. */
export function saveUrl(scenarioId: string, run: RunParts): string {
  return scenarioUrl(scenarioId, "checkpoints", runParameters(run));
}

async function made(answer: Promise<Response>): Promise<CheckpointMade> {
  try {
    const response = await answer;
    if (!response.ok) {
      return { ok: false, problem: await refusal(response) };
    }
    return { ok: true, checkpoint: parseCheckpoint(await response.json()) };
  } catch (error) {
    return { ok: false, problem: error instanceof Error ? error.message : String(error) };
  }
}

/** Saves a checkpoint at `url` (`saveUrl`). */
export function saveCheckpoint(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<CheckpointMade> {
  return made(fetchFn(url, { method: "POST" }));
}

/** Uploads a checkpoint, as the JSON a download gave. */
export function uploadCheckpoint(
  text: string,
  fetchFn: typeof fetch = fetch,
): Promise<CheckpointMade> {
  return made(
    fetchFn(CHECKPOINTS_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: text,
    }),
  );
}

/** Where a checkpoint downloads, and the file it saves as. */
export function downloadUrl(checkpoint: CheckpointSummary): string {
  return `${CHECKPOINTS_URL}/${encodeURIComponent(checkpoint.checkpointId)}`;
}

export function downloadName(checkpoint: CheckpointSummary): string {
  return `${checkpoint.scenarioId}-day-${checkpoint.day}-${checkpoint.checkpointId}.json`;
}

/** A weather's name, as the API takes it, as the address writes it: the
 * weather's own name, if not its scenario's, and its overrides. */
export function weatherParts(name: string): { weather?: string; clouds?: number; wind?: number } {
  const [clouded = "", wind] = name.split(WIND_MARK);
  const [base = DEFAULT_WEATHER, clouds] = clouded.split(CLOUDS_MARK);
  return {
    ...(base === DEFAULT_WEATHER ? {} : { weather: base }),
    ...(clouds === undefined ? {} : { clouds: Number(clouds) }),
    ...(wind === undefined ? {} : { wind: Number(wind) }),
  };
}

/** The scenario drawn as a checkpoint's run, at its moment, in its climate:
 * how the view draws its field, probes and camera stays as it was. */
export function restored(
  source: ScenarioSource,
  checkpoint: CheckpointSummary,
  field: string,
): ScenarioSource {
  const { scenarioId, fieldView, slice, probes, camera, compare } = source;
  return {
    kind: "scenario",
    scenarioId,
    ...(checkpoint.layout === "default" ? {} : { layout: checkpoint.layout }),
    ...weatherParts(checkpoint.weather),
    ...(Object.keys(checkpoint.levels).length === 0 ? {} : { levels: checkpoint.levels }),
    ...(Object.keys(checkpoint.openings).length === 0 ? {} : { openings: checkpoint.openings }),
    field,
    ...(fieldView === undefined ? {} : { fieldView }),
    ...(slice === undefined ? {} : { slice }),
    ...(compare === undefined ? {} : { compare }),
    ...(probes === undefined ? {} : { probes }),
    ...(camera === undefined ? {} : { camera }),
    ...(checkpoint.commands.length === 0 ? {} : { schedule: checkpoint.commands }),
    ...(checkpoint.daily === null ? {} : { daily: checkpoint.daily }),
    ...(checkpoint.timeS > 0 ? { time: checkpoint.timeS } : {}),
  };
}
