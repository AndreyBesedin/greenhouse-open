import { DEFAULT_WEATHER } from "../scenarios";
import type { ScenarioSource } from "../scene/edits";
import { type RunParts, runParameters, scenarioUrl } from "../scene/run";
import type { ScheduledCommand } from "../scene/source";

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

function numbers(value: unknown): value is Record<string, number> {
  return (
    typeof value === "object" &&
    value !== null &&
    !Array.isArray(value) &&
    Object.values(value).every((entry) => typeof entry === "number")
  );
}

function commandsFrom(value: unknown): ScheduledCommand[] {
  if (!Array.isArray(value)) {
    throw new Error("a checkpoint's commands are not a list");
  }
  return value.map((command: unknown) => {
    if (
      !Array.isArray(command) ||
      typeof command[0] !== "number" ||
      typeof command[1] !== "string" ||
      typeof command[2] !== "number"
    ) {
      throw new Error("a checkpoint's command is not a moment, an actuator and a level");
    }
    return { timeS: command[0], actuatorId: command[1], level: command[2] };
  });
}

/** A checkpoint as the API lists it, checked rather than trusted. */
export function parseCheckpoint(body: unknown): CheckpointSummary {
  if (typeof body !== "object" || body === null) {
    throw new Error("a checkpoint is not what the viewer expects");
  }
  const fields = body as Fields;
  const { checkpoint_id, scenario_id, layout, weather, levels, openings, day, time_s, plants } =
    fields;
  if (
    typeof checkpoint_id !== "string" ||
    typeof scenario_id !== "string" ||
    typeof layout !== "string" ||
    typeof weather !== "string" ||
    !numbers(levels) ||
    !numbers(openings) ||
    !Number.isInteger(day) ||
    typeof time_s !== "number" ||
    !Number.isInteger(plants)
  ) {
    throw new Error("a checkpoint is not what the viewer expects");
  }
  return {
    checkpointId: checkpoint_id,
    scenarioId: scenario_id,
    layout,
    weather,
    levels,
    openings,
    commands: commandsFrom(fields.commands),
    daily: fields.daily === null ? null : commandsFrom(fields.daily),
    day: day as number,
    timeS: time_s,
    plants: plants as number,
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
  try {
    const response = await fetchFn(url);
    if (!response.ok) {
      return { status: "unavailable", reason: await refusal(response) };
    }
    const body: unknown = await response.json();
    if (!Array.isArray(body)) {
      throw new Error("the checkpoints are not a list");
    }
    return { status: "loaded", checkpoints: body.map(parseCheckpoint) };
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    return { status: "unavailable", reason };
  }
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
