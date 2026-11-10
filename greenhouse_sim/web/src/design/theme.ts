import { useEffect, useState } from "react";

/** How every page looks (#208): the theme a person chose in this browser, else
 * their system's, dark if it says none (P19.12); the 3D scene and the colour
 * scales are the same in both. */
export type Theme = "dark" | "light";

// Where the choice is kept, in this browser: a person's own, never the
// address's, which describes what is shown, not how. Its name is older than this
// module's and stays, so that nobody's choice is lost.
const STORED_AS = "greenhouse-sim.panels";

/** The system's theme, as the browser says it: dark unless it says light. */
function systemTheme(): Theme {
  return typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-color-scheme: light)").matches
    ? "light"
    : "dark";
}

/** The theme last chosen in this browser, else the system's on a first visit,
 * or one whose choice reads as neither; dark if none can be read. */
export function storedTheme(): Theme {
  try {
    const chosen = localStorage.getItem(STORED_AS);
    return chosen === "light" || chosen === "dark" ? chosen : systemTheme();
  } catch {
    return "dark";
  }
}

/** Puts `theme` on the document, which `tokens.css`'s colours follow. */
export function showTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
}

/** The theme, shown on the document. One chosen is kept for the next visit; until
 * then a visit follows the system's, as it may change between visits. */
export function useTheme(): [Theme, (theme: Theme) => void] {
  const [theme, setTheme] = useState<Theme>(storedTheme);
  useEffect(() => showTheme(theme), [theme]);
  function choose(chosen: Theme): void {
    setTheme(chosen);
    try {
      localStorage.setItem(STORED_AS, chosen);
    } catch {
      // Kept for this visit only: a private window may keep nothing.
    }
  }
  return [theme, choose];
}
