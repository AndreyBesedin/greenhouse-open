import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

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

// The stylesheet's naming convention (AUDIT.20): every class is written in
// lowercase words joined by hyphens, its first word the feature that owns
// it, one of these, or else it is one of the states below, which a feature's
// class carries beside its own. A new feature's classes start with a new
// first word, added here in the same change, where review sees it.
const FEATURES = new Set([
  // The page and its panels.
  "viewer",
  "panel",
  "info",
  "inspector",
  "hud",
  "legends",
  "build",
  "debug",
  "select",
  // Choosing what is shown, and how.
  "source",
  "chooser",
  "scenario",
  "display",
  "shown",
  "category",
  "scalar",
  "swatch",
  "seen",
  // A scenario's run: its moment, playback, schedule and timeline.
  "time",
  "moment",
  "playback",
  "climate",
  "daily",
  "timeline",
  "checkpoints",
  "branches",
  "branch",
  "command",
  "controls",
  // What a run holds: its air and fields, equipment, openings, targets and weather.
  "house",
  "field",
  "probe",
  "probes",
  "equipment",
  "opening",
  "openings",
  "targets",
  "cfd",
  "weather",
  "day",
  "wind",
  // Sensors and cameras, the plants and the plant lab, moving items, QA.
  "sensor",
  "camera",
  "plant",
  "organ",
  "lab",
  "move",
  "qa",
]);
const STATES = new Set(["applied", "at-the-end", "folded", "refused", "stale"]);
const KEBAB = /^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$/;

/** The classes a stylesheet's selectors name, once each, its comments left out. */
function classesIn(stylesheet: string): string[] {
  const rules = stylesheet.replace(/\/\*[\s\S]*?\*\//g, "");
  return [
    ...new Set([...rules.matchAll(/\.([a-zA-Z][\w-]*)/g)].map(([, name]) => name ?? "")),
  ].sort();
}

/** The classes not named as the convention asks. */
function misnamed(classes: readonly string[]): string[] {
  return classes.filter(
    (name) => !STATES.has(name) && !(KEBAB.test(name) && FEATURES.has(name.split("-")[0] ?? "")),
  );
}

// The viewer's handwritten sources, which name the classes they use.
function sources(folder: string): string[] {
  return readdirSync(folder).flatMap((entry) => {
    const path = join(folder, entry);
    if (statSync(path).isDirectory()) {
      return sources(path);
    }
    return /\.tsx?$/.test(entry) && !/\.test\.tsx?$/.test(entry)
      ? [readFileSync(path, "utf8")]
      : [];
  });
}
// Classes a source builds rather than writes out, and where.
const BUILT = new Set([
  // `seen-${row.glyph}`, SeenInTheView's glyphs.
  "seen-arrow",
  "seen-dot",
  "seen-line",
]);

describe("the stylesheet's classes (AUDIT.20)", () => {
  it("are each named for the feature that owns them, or are a state", () => {
    expect(misnamed(classesIn(STYLES))).toEqual([]);
  });

  it("refuse a class named otherwise", () => {
    expect(
      misnamed(["move-list", "folded", "moveList", "move_list", "card", "panel-Column"]),
    ).toEqual(["moveList", "move_list", "card", "panel-Column"]);
  });

  it("are each named by some source, so that none is a rule left over", () => {
    const code = sources(new URL(".", import.meta.url).pathname).join("\n");
    const unused = classesIn(STYLES).filter(
      (name) => !BUILT.has(name) && !new RegExp(`(?<![\\w-])${name}(?![\\w-])`).test(code),
    );

    expect(unused).toEqual([]);
  });
});
