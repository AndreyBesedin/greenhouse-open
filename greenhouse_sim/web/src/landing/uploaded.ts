/**
 * How an uploaded scenario reaches the builder (P17.11): by its address, which
 * names the scenario, and the run settings its file held, which the start page
 * keeps for the builder in the tab's session storage. The builder reads the
 * house from the simulator, where the upload registered it.
 */

import type { RunSettings } from "../builder/api";
import type { RunFields } from "../builder/RunStep";
import { BUILDER_PATH } from "./paths";

const UPLOADED = "#scenario=";
const KEY = "greenhouse.uploaded.";

/** The builder, opened on an uploaded scenario. A fragment, so that the
 * simulator is never asked for it. */
export function uploadedAddress(scenarioId: string): string {
  return `${BUILDER_PATH}${UPLOADED}${encodeURIComponent(scenarioId)}`;
}

/** The scenario an address's fragment asks the builder to open, if it does. */
export function uploadedScenario(hash: string): string | null {
  if (!hash.startsWith(UPLOADED) || hash.length === UPLOADED.length) {
    return null;
  }
  try {
    return decodeURIComponent(hash.slice(UPLOADED.length));
  } catch {
    return null;
  }
}

/** Keeps a scenario's run settings for the builder to open it with. Storage
 * may be refused (a private window): the builder then opens it with a first
 * run's. */
export function keepSettings(scenarioId: string, settings: RunSettings): void {
  try {
    sessionStorage.setItem(`${KEY}${scenarioId}`, JSON.stringify(settings));
  } catch {
    // Not kept: the builder opens the scenario without them.
  }
}

/** The run settings kept for a scenario, as the run step's fields, if any
 * are. */
export function keptFields(scenarioId: string): RunFields | null {
  try {
    const kept: unknown = JSON.parse(sessionStorage.getItem(`${KEY}${scenarioId}`) ?? "null");
    if (typeof kept !== "object" || kept === null) {
      return null;
    }
    const { start_date, duration_days, random_seed, weather } = kept as Record<string, unknown>;
    if (
      typeof start_date !== "string" ||
      typeof duration_days !== "number" ||
      typeof random_seed !== "number" ||
      typeof weather !== "string"
    ) {
      return null;
    }
    return {
      start: start_date,
      days: String(duration_days),
      weather,
      seed: String(random_seed),
    };
  } catch {
    return null;
  }
}
