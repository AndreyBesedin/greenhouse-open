import type { Locator } from "@playwright/test";

/** The colour `element` is drawn in, and the theme's `--warn`, each as the browser
 * computes it, so that a problem drawn in another colour fails showing both. */
export function colourAndWarn(element: Locator): Promise<{ colour: string; warn: string }> {
  return element.evaluate((shown) => {
    const probe = document.createElement("span");
    probe.style.color = "var(--warn)";
    document.body.append(probe);
    const warn = getComputedStyle(probe).color;
    probe.remove();
    return { colour: getComputedStyle(shown).color, warn };
  });
}
