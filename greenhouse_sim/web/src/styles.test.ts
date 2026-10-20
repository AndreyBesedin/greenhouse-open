import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

const STYLES = readFileSync(new URL("./styles.css", import.meta.url), "utf8");
// What a panel's text or background may be: one of the theme's colours, or
// none of its own. Anything else, a colour named, written in hex or made by
// any function, stays the same whichever theme is chosen.
const THEMED = /^(?:var\(--[\w-]+\)|none|transparent|inherit|currentcolor|initial|unset)$/i;

/** The text and background colours in `stylesheet`, outside the theme's
 * own `:root` blocks, that are not the theme's. */
function unthemed(stylesheet: string): string[] {
  const rules = stylesheet.replace(/:root[^{]*\{[^}]*\}/g, "");
  // Each declaration, at a line's start or after another, or a rule's `{`.
  return [...rules.matchAll(/(?:^|[{;])\s*(color|background(?:-color)?)\s*:\s*([^;}]*)/gm)]
    .map(([, property, value]) => [property, (value ?? "").trim()])
    .filter(([, value]) => !THEMED.test(value ?? ""))
    .map(([property, value]) => `${property}: ${value};`);
}

describe("the stylesheet", () => {
  it("colours every panel's text and background from the panels' theme (#208)", () => {
    expect(unthemed(STYLES)).toEqual([]);
  });

  it("takes a colour for the theme's only when it is one of the theme's", () => {
    const written = `
      :root { --panel-bg: #111827; color: #e5e9f0; }
      .card { background: var(--panel-bg); color: var(--panel-text); }
      .named { background: white; color: Black; }
      .written { color: #444; background-color: rgb(255 255 255 / 88%); }
      .newer { color: oklch(0.7 0.1 200); background: color-mix(in srgb, red, blue); }
      .mixed { background: var(--panel-bg) url("x.png"); }
      .none { background: none; color: currentColor; }
    `;
    expect(unthemed(written)).toEqual([
      "background: white;",
      "color: Black;",
      "color: #444;",
      "background-color: rgb(255 255 255 / 88%);",
      "color: oklch(0.7 0.1 200);",
      "background: color-mix(in srgb, red, blue);",
      'background: var(--panel-bg) url("x.png");',
    ]);
  });
});
