/** The viewer's addresses (P17.5, decision 0065): a page for each. */

/** The page where a person decides what to do. */
export const LANDING_PATH = "/";
/** The setup builder, where a scenario is built or an uploaded one opened. */
export const BUILDER_PATH = "/builder";
/** The viewer, which shows a scenario or a run. */
export const VIEWER_PATH = "/view";
/** Where the project's code is, for whoever wants to contribute. */
export const REPOSITORY_URL = "https://github.com/AndreyBesedin/greenhouse-open";

/** The replay of a stored run (P17.6), whose address names its run and epoch. */
export const REPLAY_PATH = "/replay";

export type Page = "landing" | "viewer" | "replay";

/**
 * Which page an address is. The bare address is the landing page. An address
 * with a query is the viewer, as it was before the landing page: a link such as
 * `/?scenario=climate_box` still shows that scenario. So is any other path, as
 * every address but the QA pages, the builder and the replay always has been.
 */
export function pageAt(pathname: string, search: string): Page {
  const path = pathname.replace(/\/$/, "");
  if (path === REPLAY_PATH) {
    return "replay";
  }
  return path === "" && search === "" ? "landing" : "viewer";
}

/**
 * Whether a scenario opened at this path starts with its house framed: the
 * viewer's and a replay's own addresses do. A link from before the landing page,
 * `/?scenario=climate_box`, opens as it always has, at the default view, which
 * what it points out may be counted from.
 */
export function opensFramed(pathname: string): boolean {
  return pathname.replace(/\/$/, "") !== "";
}

const FOLLOW_NEWEST = "follow";

/** The replay of a stored epoch: a run's address names its run and its epoch
 * (decision 0065), and says if it opens following the newest day computed. */
export function replayAddress(runId: string, epoch: number, following = false): string {
  const follow = following ? `&${FOLLOW_NEWEST}=1` : "";
  return `${REPLAY_PATH}?run=${encodeURIComponent(runId)}&epoch=${epoch}${follow}`;
}

/** The run and epoch a replay's address names, or null if it names none that
 * can be asked for: a run, and an epoch that is a whole number. */
export function replayTarget(
  search: string,
): { runId: string; epoch: number; following: boolean } | null {
  const parameters = new URLSearchParams(search);
  const runId = parameters.get("run");
  const epoch = parameters.get("epoch");
  if (runId === null || runId === "" || epoch === null || !/^\d+$/.test(epoch)) {
    return null;
  }
  return { runId, epoch: Number(epoch), following: parameters.get(FOLLOW_NEWEST) === "1" };
}

/** The viewer's address for a scenario, with what else its address says. */
export function viewerAddress(scenarioId: string, more = ""): string {
  return `${VIEWER_PATH}?scenario=${encodeURIComponent(scenarioId)}${more}`;
}

const NEW_RUN = "#run=";

/** The landing page with the new-run form open for a scenario: where the
 * builder sends a person who has saved one. A fragment, so that it is still
 * the bare address (`pageAt`). */
export function newRunAddress(scenarioId: string): string {
  return `${LANDING_PATH}${NEW_RUN}${encodeURIComponent(scenarioId)}`;
}

const RUNS = "#runs=";

/** The landing page with a scenario's runs open, where a replay sends a
 * person to its other runs. */
export function runsAddress(scenarioId: string): string {
  return `${LANDING_PATH}${RUNS}${encodeURIComponent(scenarioId)}`;
}

/** The scenario whose runs an address's fragment asks to see, if it does. */
export function runsScenario(hash: string): string | null {
  if (!hash.startsWith(RUNS) || hash.length === RUNS.length) {
    return null;
  }
  try {
    return decodeURIComponent(hash.slice(RUNS.length));
  } catch {
    return null;
  }
}

/** The scenario whose new-run form an address's fragment asks for, if it
 * does. */
export function newRunScenario(hash: string): string | null {
  if (!hash.startsWith(NEW_RUN) || hash.length === NEW_RUN.length) {
    return null;
  }
  try {
    return decodeURIComponent(hash.slice(NEW_RUN.length));
  } catch {
    return null;
  }
}
