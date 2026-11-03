/** The viewer's addresses (P17.5, decision 0065): a page for each. */

/** The page where a person decides what to do. */
export const LANDING_PATH = "/";
/** The setup builder, where a scenario is built or an uploaded one opened. */
export const BUILDER_PATH = "/builder";
/** The viewer, which shows a scenario or a run. */
export const VIEWER_PATH = "/view";
/** Where the project's code is, for whoever wants to contribute. */
export const REPOSITORY_URL = "https://github.com/AndreyBesedin/greenhouse-open";

export type Page = "landing" | "viewer";

/**
 * Which page an address is. The bare address is the landing page. An address
 * with a query is the viewer, as it was before the landing page: a link such as
 * `/?scenario=climate_box` still shows that scenario. So is any other path, as
 * every address but the QA pages and the builder always has been.
 */
export function pageAt(pathname: string, search: string): Page {
  const path = pathname.replace(/\/$/, "");
  return path === "" && search === "" ? "landing" : "viewer";
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
