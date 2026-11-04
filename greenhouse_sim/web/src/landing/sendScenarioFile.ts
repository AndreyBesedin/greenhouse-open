/**
 * A file uploaded (P17.11), from the start page or the builder's import: the
 * simulator says which kind it is. Of a scenario file, it registers the scenario
 * and answers the house and the run settings; of an installation's, which has
 * no settings, it answers the house. Either is for the builder to open. An
 * upload never starts a run.
 */

import { type Answered, type RunSettings, readAssessed, refusal } from "../builder/api";
import type { Assessed } from "../builder/generated/assessedTypes";

/** The most of a file the simulator reads, in bytes
 * (`scenarios.scenario_files.MAX_IMPORT_BYTES`). */
export const MAX_FILE_BYTES = 8_000_000;

const BYTES_PER_MB = 1_000_000;

/** A size in megabytes of a million bytes, as the limit is. */
function megabytes(bytes: number): string {
  return `${Number((bytes / BYTES_PER_MB).toFixed(1))} MB`;
}

/** What of a scenario file's answer the start page reads: the scenario the
 * simulator registered (none if its weather is missing), the run settings its
 * file held and the recorded weather it lacked. The answer's schema is not
 * published for the viewer, since it holds the whole installation's, which the
 * page never reads: the builder asks for the house itself. */
export interface UploadedScenario {
  kind: "scenario";
  scenario: { id: string; name: string } | null;
  settings: RunSettings;
  missingWeather: string | null;
}

/** What an installation's file answers: its house, as the builder's import
 * has it. Nothing was registered. */
export interface UploadedInstallation {
  kind: "installation";
  assessed: Assessed;
}

export type Uploaded = UploadedScenario | UploadedInstallation;

/** Why a scenario file whose recorded weather is not here cannot be opened. */
export function missingWeatherProblem(fileName: string, weather: string | null): string {
  return `${fileName} runs under ${weather ?? "a recorded weather"}, which it does not carry and this simulator does not have. Ask for the file with its recorded weather included.`;
}

function record(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("not an uploaded scenario");
  }
  return value as Record<string, unknown>;
}

function readUploaded(body: unknown): Uploaded {
  const { kind, assessed, scenario, settings, missing_weather } = record(body);
  if (kind === "installation") {
    return { kind, assessed: readAssessed(assessed) };
  }
  const run = record(settings);
  const named = scenario === null ? null : record(scenario);
  const lacking = missing_weather === null ? null : record(missing_weather);
  const { start_date, duration_days, random_seed, weather } = run;
  if (
    typeof start_date !== "string" ||
    typeof duration_days !== "number" ||
    typeof random_seed !== "number" ||
    typeof weather !== "string" ||
    (named !== null && (typeof named.id !== "string" || typeof named.name !== "string")) ||
    (lacking !== null && typeof lacking.file !== "string")
  ) {
    throw new Error("not an uploaded scenario");
  }
  return {
    kind: "scenario",
    scenario: named === null ? null : { id: String(named.id), name: String(named.name) },
    settings: { start_date, duration_days, random_seed, weather },
    missingWeather: lacking === null ? null : String(lacking.file),
  };
}

/** What of a file is needed to send it: its name, size and text. */
export interface PickedFile {
  name: string;
  size: number;
  text(): Promise<string>;
}

/** A file sent to the simulator: its answer, or why the file cannot be
 * opened, in words that name the file. */
export async function uploadFile(
  file: PickedFile,
  fetchFn: typeof fetch = fetch,
): Promise<Answered<Uploaded>> {
  if (file.size > MAX_FILE_BYTES) {
    return {
      ok: false,
      problem: `${file.name} is ${megabytes(file.size)}, more than the ${megabytes(MAX_FILE_BYTES)} the simulator reads`,
    };
  }
  try {
    const response = await fetchFn("/api/scenarios/upload", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: await file.text(),
    });
    if (!response.ok) {
      return { ok: false, problem: `${file.name} cannot be opened: ${await refusal(response)}` };
    }
    return { ok: true, value: readUploaded(await response.json()) };
  } catch (error) {
    const why = error instanceof Error ? error.message : String(error);
    return { ok: false, problem: `${file.name} cannot be opened: ${why}` };
  }
}
