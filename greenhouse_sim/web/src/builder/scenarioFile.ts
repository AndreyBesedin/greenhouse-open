/**
 * A scenario's file, as the simulator serves it for a person to keep or send
 * on (P17.11): the file is read from the simulator, never made here.
 */

import { contractReader, type Loaded, loadJson } from "../loadJson";
import { refusal } from "./api";
import { SCENARIO_DOWNLOAD_SCHEMA } from "./generated/scenarioDownloadSchema";
import type { ScenarioDownload } from "./generated/scenarioDownloadTypes";

const readDownload = contractReader<ScenarioDownload>(
  SCENARIO_DOWNLOAD_SCHEMA,
  "not a scenario file",
);

/** A scenario's file, its recorded weather carried unless `withRecording`
 * is false. */
export function downloadScenarioFile(
  scenarioId: string,
  withRecording: boolean,
  fetchFn: typeof fetch = fetch,
): Promise<Loaded<ScenarioDownload>> {
  const query = withRecording ? "" : "?recording=0";
  const url = `/api/scenarios/${encodeURIComponent(scenarioId)}/file${query}`;
  return loadJson(url, readDownload, fetchFn, refusal);
}

/** The bytes a text takes in a file. */
export function bytesOf(text: string): number {
  return new Blob([text]).size;
}

/** Offers a text to the person as a file of their own to keep. */
export function offerFile(fileName: string, text: string): void {
  const url = URL.createObjectURL(new Blob([text], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}
