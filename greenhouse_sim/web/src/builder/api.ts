/**
 * The setup builder's side of the simulator's API (P12.2): its first draft
 * from the first form, an installation assessed and drawn as it is edited,
 * and its drafts saved, opened and run. Each answer is checked against the
 * contract the simulator publishes for it.
 */

import { SCENARIO_SUMMARY_SCHEMA } from "../generated/scenarioSummarySchema";
import type { ScenarioSummary } from "../generated/scenarioSummaryTypes";
import { contractReader, type Loaded, loadJson } from "../loadJson";
import { SNAPSHOT_SCHEMA } from "../scene/generated/snapshotSchema";
import type { SceneSnapshot } from "../scene/generated/snapshotTypes";
import { ASSESSED_SCHEMA } from "./generated/assessedSchema";
import type { Assessed, Installation } from "./generated/assessedTypes";
import type { BasicSetup } from "./generated/basicTypes";
import { DRAFT_SCHEMA } from "./generated/draftSchema";
import { DRAFTS_SCHEMA } from "./generated/draftsSchema";
import type { DraftsListed } from "./generated/draftsTypes";
import type { DraftAnswer } from "./generated/draftTypes";
import type { Edit } from "./generated/editTypes";

export const BUILDER_URL = "/api/builder";
export const DRAFTS_URL = "/api/drafts";

/** An answer to a request that makes something, or why it was refused, in
 * the simulator's words. */
export type Answered<T> = { ok: true; value: T } | { ok: false; problem: string };

/** What a draft's run adds to its installation (`services.drafts.DraftRun`). */
export interface RunSettings {
  scenario_id?: string;
  start_date: string;
  duration_days: number;
  random_seed: number;
  weather: string;
}

const readAssessed = contractReader<Assessed>(ASSESSED_SCHEMA, "not an assessed installation");
const readDraft = contractReader<DraftAnswer>(DRAFT_SCHEMA, "not a draft");
const readDrafts = contractReader<DraftsListed>(DRAFTS_SCHEMA, "not a list of drafts");
const readScene = contractReader<SceneSnapshot>(SNAPSHOT_SCHEMA, "not a scene");
const readScenario = contractReader<ScenarioSummary>(SCENARIO_SUMMARY_SCHEMA, "not a scenario");

/** An installation as its file writes it, in the format given: what the
 * builder sends the simulator, and what it exports. */
export function installationFile(schemaVersion: number, installation: Installation): string {
  return `${JSON.stringify({ schema_version: schemaVersion, ...installation }, null, 2)}\n`;
}

/** Why the simulator refused a request: its `error`, or its status. */
export async function refusal(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (typeof body === "object" && body !== null && "error" in body) {
      const { error } = body;
      if (typeof error === "string") {
        return error;
      }
    }
  } catch {
    // Not JSON: its status says it.
  }
  return `the simulator API answered ${response.status}`;
}

async function posted<T>(
  url: string,
  body: string,
  read: (body: unknown) => T,
  fetchFn: typeof fetch,
): Promise<Answered<T>> {
  try {
    const response = await fetchFn(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });
    if (!response.ok) {
      return { ok: false, problem: await refusal(response) };
    }
    return { ok: true, value: read(await response.json()) };
  } catch (error) {
    return { ok: false, problem: error instanceof Error ? error.message : String(error) };
  }
}

/** The first draft the first form's values describe, assessed. */
export function firstDraft(values: BasicSetup, fetchFn: typeof fetch = fetch) {
  return posted(`${BUILDER_URL}/basic`, JSON.stringify(values), readAssessed, fetchFn);
}

/** A scenario's house as an installation, assessed, named as the scenario
 * is, for the builder to copy. */
export function scenarioHouse(
  scenarioId: string,
  fetchFn: typeof fetch = fetch,
): Promise<Loaded<Assessed>> {
  const url = `/api/scenarios/${encodeURIComponent(scenarioId)}/installation`;
  return loadJson(url, readAssessed, fetchFn, refusal);
}

/** An installation's file read and assessed as it stands. */
export function assess(file: string, fetchFn: typeof fetch = fetch) {
  return posted(`${BUILDER_URL}/assess`, file, readAssessed, fetchFn);
}

/** An edit of many items (P12.3) made on an installation, in the format
 * given: the installation it makes, assessed, or why the simulator refused
 * the edit. The installation edited is not changed, for an undo. */
export function edit(
  schemaVersion: number,
  installation: Installation,
  change: Edit,
  fetchFn: typeof fetch = fetch,
): Promise<Answered<Assessed>> {
  const body = JSON.stringify({
    file: { schema_version: schemaVersion, ...installation },
    edit: change,
  });
  return posted(`${BUILDER_URL}/edit`, body, readAssessed, fetchFn);
}

/** The house an installation's file describes, as a scene. */
export function preview(file: string, fetchFn: typeof fetch = fetch) {
  return posted(`${BUILDER_URL}/scene`, file, readScene, fetchFn);
}

function draftUrl(draftId: string, action = "", query: Record<string, string> = {}): string {
  const parameters = new URLSearchParams(query).toString();
  const path = `${DRAFTS_URL}/${encodeURIComponent(draftId)}${action === "" ? "" : `/${action}`}`;
  return parameters === "" ? path : `${path}?${parameters}`;
}

/** The drafts kept, each at its latest revision. */
export function loadDrafts(fetchFn: typeof fetch = fetch): Promise<Loaded<DraftsListed>> {
  return loadJson(DRAFTS_URL, readDrafts, fetchFn, refusal);
}

/** A draft at a revision, by default its latest. */
export function openDraft(
  draftId: string,
  revision: number | null = null,
  fetchFn: typeof fetch = fetch,
): Promise<Loaded<DraftAnswer>> {
  const query: Record<string, string> = revision === null ? {} : { revision: String(revision) };
  return loadJson(draftUrl(draftId, "", query), readDraft, fetchFn, refusal);
}

/** An installation's file saved as a draft's next revision, made on
 * revision `on`, or as a new draft if null. */
export function saveDraft(
  draftId: string,
  file: string,
  on: number | null,
  fetchFn: typeof fetch = fetch,
): Promise<Answered<DraftAnswer>> {
  const query: Record<string, string> = on === null ? {} : { on: String(on) };
  return posted(draftUrl(draftId, "save", query), file, readDraft, fetchFn);
}

/** A draft at a revision run as a scenario of its own, registered. */
export function runDraft(
  draftId: string,
  revision: number,
  settings: RunSettings,
  fetchFn: typeof fetch = fetch,
): Promise<Answered<ScenarioSummary>> {
  const url = draftUrl(draftId, "run", { revision: String(revision) });
  return posted(url, JSON.stringify(settings), readScenario, fetchFn);
}
