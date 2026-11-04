import { useEffect, useState } from "react";

/** How every page looks (#208): dark by default, light if the person chose it;
 * the 3D scene and the colour scales are the same in both. */
export type Theme = "dark" | "light";

// Where the choice is kept, in this browser: a person's own, never the
// address's, which describes what is shown, not how. Its name is older than this
// module's and stays, so that nobody's choice is lost.
const STORED_AS = "greenhouse-sim.panels";

/** The theme last chosen in this browser, dark if none was, or if it cannot
 * be read. */
export function storedTheme(): Theme {
  try {
    return localStorage.getItem(STORED_AS) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

/** Puts `theme` on the document, which `tokens.css`'s colours follow. */
export function showTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
}

/** The theme, shown on the document and kept for the next visit. */
export function useTheme(): [Theme, (theme: Theme) => void] {
  const [theme, setTheme] = useState<Theme>(storedTheme);
  useEffect(() => {
    showTheme(theme);
    try {
      localStorage.setItem(STORED_AS, theme);
    } catch {
      // Kept for this visit only: a private window may keep nothing.
    }
  }, [theme]);
  return [theme, setTheme];
}
