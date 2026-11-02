/** The viewer's addresses (P17.5, decision 0065): a page for each. */

/** The page where a person decides what to do. */
export const LANDING_PATH = "/";
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
