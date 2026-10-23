import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

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

/** The classes a stylesheet's selectors name, once each: read from each
 * rule's and at-rule's prelude, the text before its block opens, its
 * comments and quoted text left out, so that no declaration, such as
 * `url("./icon.svg")`, names a class. */
function classesIn(stylesheet: string): string[] {
  const text = stylesheet
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'/g, '""');
  const preludes = [...text.matchAll(/([^{};]*)\{/g)].map(([, prelude]) => prelude ?? "");
  return [
    ...new Set(
      preludes.flatMap((prelude) =>
        [...prelude.matchAll(/\.([a-zA-Z][\w-]*)/g)].map(([, name]) => name ?? ""),
      ),
    ),
  ].sort();
}

/** The classes not named as the convention asks. */
function misnamed(classes: readonly string[]): string[] {
  return classes.filter(
    (name) => !STATES.has(name) && !(KEBAB.test(name) && FEATURES.has(name.split("-")[0] ?? "")),
  );
}

// The viewer's handwritten sources, which give elements their classes.
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
/** The end of the value that starts at `start`: a string's closing quote,
 * or the brace that closes a JSX expression. */
function valueEnd(source: string, start: number): number {
  const opening = source[start];
  if (opening !== "{") {
    return source.indexOf(opening ?? "", start + 1);
  }
  let depth = 0;
  for (let at = start; at < source.length; at += 1) {
    depth += source[at] === "{" ? 1 : source[at] === "}" ? -1 : 0;
    if (depth === 0) {
      return at;
    }
  }
  return source.length;
}

/** The classes a source gives elements: every word of every string written
 * as a `className`, a JSX attribute's (`className="…"`, `className={…}`), an
 * object's property (`className: "…"`) or a DOM element's (`.className =
 * "…"`). A word that is only a test id, a label or a comment is none. */
function classesAssigned(source: string): Set<string> {
  const assigned = new Set<string>();
  for (const match of source.matchAll(/className\s*[=:]\s*/g)) {
    const start = (match.index ?? 0) + match[0].length;
    const value = source.slice(start, valueEnd(source, start) + 1);
    // Its quoted strings, those inside a template's expressions too, and each
    // template's own text, its expressions left out.
    const strings = [
      ...[...value.matchAll(/"([^"]*)"|'([^']*)'/g)].map(([, double, single]) => double ?? single),
      ...[...value.matchAll(/`([^`]*)`/g)].map(([, template]) =>
        (template ?? "").replace(/\$\{[^}]*\}/g, " "),
      ),
    ];
    for (const word of strings.flatMap((text) => (text ?? "").split(/\s+/))) {
      assigned.add(word);
    }
  }
  return assigned;
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

  it("are read from the selectors alone", () => {
    const written = `
      /* .commented { } */
      .a { background: url("./icon.svg"); }
      .b::after { content: ".quoted"; }
      @media (min-resolution: 1.5dppx) { .c, .d > .e { color: inherit; } }
    `;
    expect(classesIn(written)).toEqual(["a", "b", "c", "d", "e"]);
  });

  it("are each given to an element by some source, so that none is a rule left over", () => {
    const assigned = new Set(
      sources(fileURLToPath(new URL(".", import.meta.url))).flatMap((source) => [
        ...classesAssigned(source),
      ]),
    );
    const unused = classesIn(STYLES).filter((name) => !BUILT.has(name) && !assigned.has(name));

    expect(unused).toEqual([]);
  });

  it("count a class given, not a word that is only a test id, a label or a comment", () => {
    const source = [
      "// .gone-in-a-comment",
      '<div data-testid="only-an-id" className={open ? "hud" : "hud folded"}>',
      // biome-ignore lint/suspicious/noTemplateCurlyInString: a source's text, its template written out
      '  <span className={`${now ? "applied" : "to-come"}${every ? " daily" : ""}`} />',
      // biome-ignore lint/suspicious/noTemplateCurlyInString: a source's text, its template written out
      "  <span className={`seen-glyph seen-${glyph}`} />",
      '  <span className="weather-day-row">label-only</span>',
      "</div>;",
      'const columns = [{ className: "day-wind" }];',
      "element.className = 'debug-label';",
    ].join("\n");
    expect([...classesAssigned(source)].filter((word) => word !== "").sort()).toEqual([
      "applied",
      "daily",
      "day-wind",
      "debug-label",
      "folded",
      "hud",
      "seen-",
      "seen-glyph",
      "to-come",
      "weather-day-row",
    ]);
  });
});
