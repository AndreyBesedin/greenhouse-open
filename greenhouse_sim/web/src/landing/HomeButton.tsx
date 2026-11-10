import { HomeIcon } from "../icons";
import { LANDING_PATH } from "./paths";

/** What the way home says on hover (P22.9). */
export const HOME_NOTE = "Go to the start page";

/**
 * The way back to the landing page, at the top left of the viewer and of a
 * replay (P17.6): a house, and the word, so that it is named to whoever
 * hears it and read by whoever sees it. A plain link, so that the browser
 * opens the page as it opens any other address.
 */
export function HomeButton() {
  return (
    <a href={LANDING_PATH} className="home-button" data-testid="home-button" title={HOME_NOTE}>
      <HomeIcon />
      Home
    </a>
  );
}
