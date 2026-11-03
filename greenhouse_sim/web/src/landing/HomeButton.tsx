import { LANDING_PATH } from "./paths";

/**
 * The way back to the landing page, at the top left of the viewer and of a
 * replay (P17.6): a house, and the word, so that it is named to whoever
 * hears it and read by whoever sees it. A plain link, so that the browser
 * opens the page as it opens any other address.
 */
export function HomeButton() {
  return (
    <a href={LANDING_PATH} className="home-button" data-testid="home-button">
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M3 11l9-8 9 8" />
        <path d="M5 10v10h5v-6h4v6h5V10" />
      </svg>
      Home
    </a>
  );
}
