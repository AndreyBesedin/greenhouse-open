import type { Locator } from "@playwright/test";

// The tokens a ring may be drawn in, by name, so that a ring reads as one.
const RING_COLOURS = ["--action", "--text"] as const;

/** The ring `element` shows, as "style width offset colour", its colour by the
 * token it computes to when it is one of `RING_COLOURS`, as the browser computes
 * each in the page's theme. */
export function focusRing(element: Locator): Promise<string> {
  return element.evaluate((shown, tokens) => {
    const style = getComputedStyle(shown);
    const probe = document.createElement("span");
    document.body.append(probe);
    const named = tokens.find((token) => {
      probe.style.color = `var(${token})`;
      return getComputedStyle(probe).color === style.outlineColor;
    });
    probe.remove();
    return [
      style.outlineStyle,
      style.outlineWidth,
      style.outlineOffset,
      named ?? style.outlineColor,
    ].join(" ");
  }, RING_COLOURS);
}
