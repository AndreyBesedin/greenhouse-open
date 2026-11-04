// The design system's reference page, its address and theme, kept free of imports
// but a type's, so that browser tests can read it too.

import type { Theme } from "../design/theme";

export const QA_DESIGN_PATH = "/qa/design";

/** The page's address in `theme`. */
export function designAddress(theme: Theme): string {
  return `${QA_DESIGN_PATH}?theme=${theme}`;
}

/** The theme its address asks for: light, as every QA page's, unless it says dark.
 * It reads no person's choice and keeps none. */
export function designTheme(search: string): Theme {
  return new URLSearchParams(search).get("theme") === "dark" ? "dark" : "light";
}
