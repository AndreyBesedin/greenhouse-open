/**
 * How an uploaded file reaches the builder (P17.11): by its address. A scenario's
 * names the scenario, and the start page keeps the run settings its file held for
 * the builder in the tab's session storage; the builder reads the house from the
 * simulator, where the upload registered it. An installation's is registered
 * nowhere, so the start page keeps the file there for the builder to read.
 */

import type { RunSettings } from "../builder/api";
import type { RunFields } from "../builder/RunStep";
import { BUILDER_PATH } from "./paths";

const UPLOADED = "#scenario=";
const KEY = "greenhouse.uploaded.";
const UPLOADED_HOUSE = "#installation=";
const HOUSE_KEY = "greenhouse.uploaded-house.";

/** The builder, opened on an uploaded scenario. A fragment, so that the
 * simulator is never asked for it. */
export function uploadedAddress(scenarioId: string): string {
  return `${BUILDER_PATH}${UPLOADED}${encodeURIComponent(scenarioId)}`;
}

/** The builder, opened on an uploaded installation's file. */
export function uploadedHouseAddress(installationId: string): string {
  return `${BUILDER_PATH}${UPLOADED_HOUSE}${encodeURIComponent(installationId)}`;
}

function named(hash: string, prefix: string): string | null {
  if (!hash.startsWith(prefix) || hash.length === prefix.length) {
    return null;
  }
  try {
    return decodeURIComponent(hash.slice(prefix.length));
  } catch {
    return null;
  }
}

/** The scenario an address's fragment asks the builder to open, if it does. */
export function uploadedScenario(hash: string): string | null {
  return named(hash, UPLOADED);
}

/** The installation an address's fragment asks the builder to open, if it does. */
export function uploadedHouse(hash: string): string | null {
  return named(hash, UPLOADED_HOUSE);
}

/** An installation's file, as the builder is to read it, and the name it was
 * uploaded under. */
export interface KeptHouse {
  fileName: string;
  text: string;
}

/** Keeps an installation's file for the builder to open it; whether it was
 * kept. Storage may be refused (a private window) or too small for the file. */
export function keepHouse(installationId: string, house: KeptHouse): boolean {
  try {
    sessionStorage.setItem(`${HOUSE_KEY}${installationId}`, JSON.stringify(house));
    return true;
  } catch {
    return false;
  }
}

/** The installation's file kept in this tab, if it is. */
export function keptHouse(installationId: string): KeptHouse | null {
  try {
    const kept: unknown = JSON.parse(
      sessionStorage.getItem(`${HOUSE_KEY}${installationId}`) ?? "null",
    );
    if (typeof kept !== "object" || kept === null) {
      return null;
    }
    const { fileName, text } = kept as Record<string, unknown>;
    return typeof fileName === "string" && typeof text === "string" ? { fileName, text } : null;
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
