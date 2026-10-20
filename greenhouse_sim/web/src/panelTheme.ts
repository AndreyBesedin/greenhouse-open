import { useEffect, useState } from "react";

/** How the panels over the view look (#208): dark by default, light if the
 * person chose it; the 3D scene and the colour scales are the same in both. */
export type PanelTheme = "dark" | "light";

// Where the choice is kept, in this browser: a person's own, never the
// address's, which describes what is shown, not how.
const STORED_AS = "greenhouse-sim.panels";

/** The theme last chosen in this browser, dark if none was, or if it cannot
 * be read. */
export function storedPanelTheme(): PanelTheme {
  try {
    return localStorage.getItem(STORED_AS) === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
}

/** Puts `theme` on the document, which the stylesheet's colours follow. */
export function showPanels(theme: PanelTheme): void {
  document.documentElement.dataset.panels = theme;
}

/** The panels' theme, shown on the document and kept for the next visit. */
export function usePanelTheme(): [PanelTheme, (theme: PanelTheme) => void] {
  const [theme, setTheme] = useState<PanelTheme>(storedPanelTheme);
  useEffect(() => {
    showPanels(theme);
    try {
      localStorage.setItem(STORED_AS, theme);
    } catch {
      // Kept for this visit only: a private window may keep nothing.
    }
  }, [theme]);
  return [theme, setTheme];
}
