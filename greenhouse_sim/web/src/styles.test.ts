import { createHash } from "node:crypto";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { SUN_COLOR, WIND_COLOR } from "./weather/weather";

/** A stylesheet's text with each `@import` in its place, in the build's order. */
function withImports(
  path: string,
  read: (path: string) => string = (file) => readFileSync(file, "utf8"),
): string {
  return read(path).replace(/^@import\s+"([^"]+)";[^\S\n]*$/gm, (_line, imported: string) =>
    withImports(join(dirname(path), imported), read),
  );
}

/** The stylesheets `path` is made of, itself first, each as it was written. */
function importedStylesheets(
  path: string,
  read: (path: string) => string = (file) => readFileSync(file, "utf8"),
): { path: string; text: string }[] {
  const text = read(path);
  return [
    { path, text },
    ...[...text.matchAll(/^@import\s+"([^"]+)";[^\S\n]*$/gm)].flatMap(([, imported]) =>
      importedStylesheets(join(dirname(path), imported ?? ""), read),
    ),
  ];
}

const ENTRY = fileURLToPath(new URL("./styles.css", import.meta.url));
const STYLES = withImports(ENTRY);
// What a panel's text or background may be: one of the theme's colours, or
// none of its own. Anything else, a colour named, written in hex or made by
// any function, stays the same whichever theme is chosen.
const THEMED = /^(?:var\(--[\w-]+\)|none|transparent|inherit|currentcolor|initial|unset)$/i;
// Or a pattern drawn in the theme's colours, such as the replay's hatching.
const THEMED_PATTERN = /^repeating-linear-gradient\(/;

/** The text and background colours in `stylesheet`, outside the theme's
 * own `:root` blocks, that are not the theme's. */
function unthemed(stylesheet: string): string[] {
  const rules = stylesheet.replace(/:root[^{]*\{[^}]*\}/g, "");
  // Each declaration, at a line's start or after another, or a rule's `{`.
  return [...rules.matchAll(/(?:^|[{;])\s*(color|background(?:-color)?)\s*:\s*([^;}]*)/gm)]
    .map(([, property, value]) => [property, (value ?? "").trim()])
    .filter(
      ([, value]) =>
        !THEMED.test(value ?? "") &&
        !(THEMED_PATTERN.test(value ?? "") && !RAW_COLOUR.test(value ?? "")),
    )
    .map(([property, value]) => `${property}: ${value};`);
}

// A colour in a value: written in hex, made by a function, or named. `color-mix`
// is not one by itself: what it mixes is read as any other value, so that the
// text's own colour may be mixed and a written one may not.
const RAW_COLOUR = new RegExp(
  [
    "#[0-9a-f]{3,8}\\b",
    "\\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|light-dark)\\(",
    "(?<![\\w-])(?:black|silver|gr[ae]y|white|maroon|red|purple|fuchsia|magenta|green|lime|olive|yellow|navy|blue|teal|aqua|cyan|orange|pink|brown)(?![\\w-])",
  ].join("|"),
  "i",
);

/** Every declaration in `stylesheet`, outside the tokens' `:root` blocks, that
 * writes a colour rather than naming a token. */
function rawColours(stylesheet: string): string[] {
  const rules = stylesheet.replace(/\/\*[\s\S]*?\*\//g, "").replace(/:root[^{]*\{[^}]*\}/g, "");
  return [...rules.matchAll(/(?:^|[{;])\s*([a-z-]+)\s*:\s*([^;{}]*)/gm)]
    .map(([, property, value]) => [property, (value ?? "").trim()])
    .filter(([, value]) => RAW_COLOUR.test(value ?? ""))
    .map(([property, value]) => `${property}: ${value};`);
}

// What a colour token may be, by the role it has: a new one is added here, where
// review sees it (decision 0068).
const COLOUR_ROLE =
  /^--(?:surface-\w+|text(?:-\w+)?|border|action|warn|mark|scheme|chart-[\w-]+|data-\w+)$/;

// And the size tokens, each scale's steps written out, so that a new step is too.
const SIZE_STEP =
  /^--(?:font-(?:xs|sm|md|lg|xl|[234]xl)|radius-(?:sm|md|lg|xl|pill)|space-[1-9]|focus-(?:width|offset)|target(?:-compact)?)$/;

function misnamedTokens(names: Iterable<string>): string[] {
  return [...names].filter((name) => !COLOUR_ROLE.test(name) && !SIZE_STEP.test(name));
}

describe("the stylesheet", () => {
  it("colours every panel's text and background from the panels' theme (#208)", () => {
    expect(unthemed(STYLES)).toEqual([]);
  });

  it("sets the info panel's line height, so that its height does not hang on the system's font (#273)", () => {
    const rule = /(?:^|\})\s*\.info-panel\s*\{([^}]*)\}/.exec(STYLES)?.[1] ?? "";
    expect(rule.replace(/\/\*[\s\S]*?\*\//g, "")).toMatch(/line-height:\s*[\d.]+;/);
  });

  it("writes a colour nowhere but in the tokens (P19.2)", () => {
    expect(rawColours(STYLES)).toEqual([]);
  });

  it("takes a colour for raw in any declaration, and not a name that holds one's word", () => {
    const written = `
      /* #111 in a comment, and red. */
      :root { --ink: #111111; }
      .a { stroke: #c0392b; fill: rgb(0 0 0 / 50%); border: 1px solid Red; }
      .b { box-shadow: 0 0 2px oklch(0.7 0.1 200); outline-color: navy; }
      .c { stroke: var(--data-red); color: var(--chart-blue-text); fill: none; }
      .d { background: var(--replay-green-track); transition: color 1s; }
      #root:hover .e { gap: 2px; }
      .f { border-top: 1px solid color-mix(in srgb, currentColor 25%, transparent); }
      .g { border-top: 1px solid color-mix(in srgb, #fff 25%, transparent); }
    `;
    expect(rawColours(written)).toEqual([
      "stroke: #c0392b;",
      "fill: rgb(0 0 0 / 50%);",
      "border: 1px solid Red;",
      "box-shadow: 0 0 2px oklch(0.7 0.1 200);",
      "outline-color: navy;",
      "border-top: 1px solid color-mix(in srgb, #fff 25%, transparent);",
    ]);
  });

  it("names each colour for what it does, and each size for its scale (P19.3, P19.4)", () => {
    expect(misnamedTokens(tokenValues(STYLES, "dark").keys())).toEqual([]);
  });

  it("refuses a token named for a place, or a step no scale has", () => {
    expect(
      misnamedTokens([
        "--text-soft",
        "--font-2xl",
        "--radius-pill",
        "--target",
        "--target-compact",
        "--space-9",
        "--panel-text",
        "--landing-bg",
        "--textual",
        "--font-13",
        "--font-5xl",
        "--radius",
        "--target-small",
        "--space-10",
        "--space",
      ]),
    ).toEqual([
      "--panel-text",
      "--landing-bg",
      "--textual",
      "--font-13",
      "--font-5xl",
      "--radius",
      "--target-small",
      "--space-10",
      "--space",
    ]);
  });

  it("gives a chart's wind and sun the colours the scene gives them", () => {
    const tokens = tokenValues(STYLES, "dark");
    expect(tokens.get("--data-blue")).toBe(WIND_COLOR);
    expect(tokens.get("--data-amber")).toBe(SUN_COLOR);
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
      .hatched { background: repeating-linear-gradient(135deg, var(--ink) 0 3px, transparent 3px 6px); }
      .written-hatch { background: repeating-linear-gradient(135deg, #ccc 0 3px, transparent 3px 6px); }
    `;
    expect(unthemed(written)).toEqual([
      "background: white;",
      "color: Black;",
      "color: #444;",
      "background-color: rgb(255 255 255 / 88%);",
      "color: oklch(0.7 0.1 200);",
      "background: color-mix(in srgb, red, blue);",
      'background: var(--panel-bg) url("x.png");',
      "background: repeating-linear-gradient(135deg, #ccc 0 3px, transparent 3px 6px);",
    ]);
  });
});

// The least contrast each kind of thing needs (WCAG 2.2's 1.4.3 and 1.4.11).
const TEXT_NEEDS = 4.5;
const MARK_NEEDS = 3;
// What sits on what, as the stylesheet has it: a new colour for text, a line or an
// outline is added here, where review sees it (decision 0068).
const SITS_ON: readonly { needs: number; what: readonly string[]; on: readonly string[] }[] = [
  {
    needs: TEXT_NEEDS,
    what: ["--text", "--text-soft", "--text-muted", "--action", "--warn"],
    on: ["--surface-page", "--surface-panel"],
  },
  // The words of a label over the scene; a pressed button's; a chart key's; a compass's N.
  { needs: TEXT_NEEDS, what: ["--text"], on: ["--surface-label"] },
  { needs: TEXT_NEEDS, what: ["--surface-page"], on: ["--action"] },
  { needs: TEXT_NEEDS, what: ["--chart-soft", "--chart-blue-text"], on: ["--surface-panel"] },
  { needs: TEXT_NEEDS, what: ["--text-muted"], on: ["--chart-face"] },
  // A control's outline: a field's, a plain button's, a primary's, a danger's.
  {
    needs: MARK_NEEDS,
    what: ["--border", "--text-muted", "--action", "--warn"],
    on: ["--surface-page", "--surface-panel"],
  },
  // A chart's lines, in its panel; a compass's on its face.
  {
    needs: MARK_NEEDS,
    what: [
      "--data-amber",
      "--data-blue",
      "--data-green",
      "--data-navy",
      "--data-orange",
      "--data-red",
      "--data-sky",
      "--chart-ring",
      "--chart-neutral",
      "--chart-strong",
      "--chart-soft",
      "--chart-off",
      "--chart-faint",
    ],
    on: ["--surface-panel"],
  },
  { needs: MARK_NEEDS, what: ["--chart-ring", "--data-blue"], on: ["--chart-face"] },
];

// What falls short today, computed: each is taken out by the visual step that fixes
// it (P19.12), and the test fails if one is left here once fixed, or if one more falls.
const CONTRAST_FAILURES: Readonly<Record<string, number>> = {
  // Words: a chart key's.
  "dark: --chart-soft on --surface-panel, needs 4.5": 4.36,
  "light: --chart-soft on --surface-panel, needs 4.5": 2.7,
  "light: --chart-blue-text on --surface-panel, needs 4.5": 3.94,
  // A control's only outline: the words of a button identify it, a field's do not.
  "dark: --border on --surface-page, needs 3": 2.09,
  "dark: --border on --surface-panel, needs 3": 1.49,
  "light: --border on --surface-page, needs 3": 1.48,
  "light: --border on --surface-panel, needs 3": 1.22,
  // A chart's lines, the same in both themes, which show on one of them.
  "dark: --data-blue on --surface-panel, needs 3": 2.96,
  "dark: --data-navy on --surface-panel, needs 3": 2.58,
  "dark: --data-red on --surface-panel, needs 3": 2.46,
  "light: --data-amber on --surface-panel, needs 3": 1.6,
  "light: --data-orange on --surface-panel, needs 3": 1.77,
  // A chart's neutral lines, and a compass's ring.
  "dark: --chart-faint on --surface-panel, needs 3": 2.47,
  "light: --chart-faint on --surface-panel, needs 3": 1.46,
  "light: --chart-off on --surface-panel, needs 3": 2.64,
  "light: --chart-soft on --surface-panel, needs 3": 2.7,
  "light: --chart-ring on --surface-panel, needs 3": 2.17,
  "light: --chart-ring on --chart-face, needs 3": 2.85,
};

interface Colour {
  red: number;
  green: number;
  blue: number;
  alpha: number;
}

/** A token's colour, as `tokens.css` writes them: `#rrggbb`, or `rgb(r g b / a%)`. */
function colourOf(written: string): Colour {
  const hex = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(written);
  if (hex !== null) {
    const [red, green, blue] = hex.slice(1).map((part) => Number.parseInt(part, 16));
    return { red: red ?? 0, green: green ?? 0, blue: blue ?? 0, alpha: 1 };
  }
  const rgb = /^rgb\((\d+) (\d+) (\d+) \/ (\d+)%\)$/.exec(written);
  if (rgb !== null) {
    const [red, green, blue, percent] = rgb.slice(1).map(Number);
    return { red: red ?? 0, green: green ?? 0, blue: blue ?? 0, alpha: (percent ?? 0) / 100 };
  }
  throw new Error(`no colour in ${written}`);
}

function over(top: Colour, ground: Colour): Colour {
  const mixed = (part: "red" | "green" | "blue"): number =>
    top.alpha * top[part] + (1 - top.alpha) * ground[part];
  return { red: mixed("red"), green: mixed("green"), blue: mixed("blue"), alpha: 1 };
}

function luminance({ red, green, blue }: Colour): number {
  const linear = (level: number): number => {
    const share = level / 255;
    return share <= 0.04045 ? share / 12.92 : ((share + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * linear(red) + 0.7152 * linear(green) + 0.0722 * linear(blue);
}

function ratio(one: Colour, other: Colour): number {
  const [low, high] = [luminance(one), luminance(other)].sort((a, b) => a - b);
  return ((high ?? 0) + 0.05) / ((low ?? 0) + 0.05);
}

const WHITE: Colour = { red: 255, green: 255, blue: 255, alpha: 1 };
const BLACK: Colour = { red: 0, green: 0, blue: 0, alpha: 1 };

/** `ink`'s contrast on `surface` at its worst: what lies behind a translucent surface
 * can be anything, between white and black, and a translucent ink lets the surface
 * through in turn. */
function worstContrast(ink: Colour, surface: Colour): number {
  return Math.min(
    ...[WHITE, BLACK].map((backdrop) => {
      const ground = over(surface, backdrop);
      return ratio(over(ink, ground), ground);
    }),
  );
}

/** Each pair of `pairs` under what it needs, in `stylesheet`'s themes, by name, with
 * the contrast it has to two places. */
function contrastFailures(stylesheet: string, pairs = SITS_ON): Record<string, number> {
  const failures: Record<string, number> = {};
  for (const theme of ["dark", "light"] as const) {
    const tokens = tokenValues(stylesheet.replace(COMMENT, ""), theme);
    const colour = (name: string): Colour => {
      const written = tokens.get(name);
      if (written === undefined) {
        throw new Error(`${name} is declared here and never defined`);
      }
      return colourOf(written.trim());
    };
    for (const { needs, what, on } of pairs) {
      for (const ink of what) {
        for (const surface of on) {
          const contrast = worstContrast(colour(ink), colour(surface));
          if (contrast < needs) {
            const key = `${theme}: ${ink} on ${surface}, needs ${needs}`;
            failures[key] = Number(contrast.toFixed(2));
          }
        }
      }
    }
  }
  return failures;
}

describe("the tokens' contrast (P19.6)", () => {
  it("falls short only where it is listed, in both themes", () => {
    expect(contrastFailures(STYLES)).toEqual(CONTRAST_FAILURES);
  });

  it("is WCAG's ratio, at the worst backdrop", () => {
    expect(ratio(BLACK, WHITE)).toBeCloseTo(21, 5);
    expect(ratio(colourOf("#777777"), WHITE)).toBeCloseTo(4.48, 2);
    // A panel 90% dark over white is at its lightest, and light text at its worst.
    const panel = colourOf("rgb(17 24 39 / 90%)");
    expect(worstContrast(colourOf("#e5e9f0"), panel)).toBeCloseTo(11, 1);
    expect(worstContrast(colourOf("#000000"), colourOf("rgb(255 255 255 / 88%)"))).toBeCloseTo(
      15.97,
      1,
    );
    expect(worstContrast(WHITE, BLACK)).toBeCloseTo(21, 5);
  });

  it("draws translucent words or lines over what they sit on, not as if opaque", () => {
    const panel = colourOf("rgb(17 24 39 / 90%)");
    expect(worstContrast(colourOf("rgb(229 233 240 / 1%)"), panel)).toBeLessThan(1.1);
    expect(worstContrast(colourOf("rgb(255 255 255 / 50%)"), BLACK)).toBeCloseTo(5.28, 1);

    const faded = STYLES.replace("--text: #e5e9f0", "--text: rgb(229 233 240 / 1%)");
    expect(contrastFailures(faded)).toHaveProperty(["dark: --text on --surface-panel, needs 4.5"]);
  });

  it("is computed per theme, and reads a change of a token in one of them", () => {
    const written = `
      :root { --ink: #777777; --ground: #ffffff; }
      :root[data-theme="light"] { --ink: #000000; }
    `;
    const pairs = [{ needs: 4.5, what: ["--ink"], on: ["--ground"] }];
    expect(contrastFailures(written, pairs)).toEqual({
      "dark: --ink on --ground, needs 4.5": 4.48,
    });
    expect(contrastFailures(written.replace("--ink: #777777", "--ink: #767676"), pairs)).toEqual(
      {},
    );
  });

  it("refuses a pair whose token is gone, and a colour it cannot read", () => {
    const pairs = [{ needs: 3, what: ["--gone"], on: ["--ground"] }];
    expect(() => contrastFailures(":root { --ground: #ffffff; }", pairs)).toThrow("--gone");
    expect(() => colourOf("red")).toThrow("red");
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
  // The setup builder's page (P12.2), and the page before it (P17.5), and the
  // way back to it from the viewer.
  "builder",
  "landing",
  "home",
  // A stored run replayed (P17.6): its header, scene, transport and timeline.
  "replay",
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
  // The design system's components (P19.6), whose rules stand in `src/design/` alone.
  "ds",
]);
// `visually-hidden` is said to whoever hears the page and not shown.
const STATES = new Set(["applied", "at-the-end", "folded", "refused", "stale", "visually-hidden"]);
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
  // `timeline-plan-${name}`, a followed run's plan lane's ticks (P13.8).
  "timeline-plan-ran",
  "timeline-plan-not-ran",
  "timeline-plan-to-come",
  // `landing-status-${run.status}`, a stored run's status on the landing page (P17.5).
  "landing-status-failed",
  "landing-status-interrupted",
  "landing-status-queued",
  "landing-status-running",
  // `buttonClass`: what is drawn as a button, by its tone and size (P19.6).
  "ds-button",
  "ds-button-primary",
  "ds-button-danger",
  "ds-button-compact",
  // `StatusChip` by its tone (P19.7).
  "ds-status-chip",
  "ds-status-chip-active",
  "ds-status-chip-problem",
  // `Notice` by its kind (P19.7).
  "ds-notice",
  "ds-notice-problem",
  // `Field`'s control by its size (P19.9).
  "ds-field-control",
  "ds-field-control-compact",
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

// The stylesheet as the browser takes it, in each theme, by digest (P19.1). While
// tokens replace written values (P19.2 to P19.5), this does not change: equal text
// in equal order is an equal cascade, and custom properties stand on `:root` alone
// (below), so that replacing each `var()` is what the browser computes.
//
// A pull request that means to change a style writes the digests the test
// prints here, in its own diff, where review sees them; a token step must not. The
// components' rules stand outside it: the reference page's baselines hold those, and
// adding them moves nothing a page draws.
//
// A page's rules cut into a stylesheet of their own come before the viewer's, which
// changes their order, and so these digests: the pull request says what shows that
// the order changes nothing (the builder's, P19.9). It goes in P19.8. Until then it
// holds what nothing else does: at `c0262394`, 206 of the stylesheet's 370 rules
// match nothing on the pages the no-tolerance baselines draw, and the guards below
// read how a value is written, not which it is.
const RESOLVED_DIGESTS = {
  dark: "25b59e0f4aaa08b067902435416d42c506c3186bfc9a2fcd22de8a62044f1883",
  light: "f6e24a33f232091b13bf6a0beee5efa97ef87433eef510293b3ad5ff1feff18e",
};
type ThemeName = keyof typeof RESOLVED_DIGESTS;
const STYLES_OF_THE_PAGES = withImports(ENTRY, (file) =>
  file.endsWith("/design/components.css") ? "" : readFileSync(file, "utf8"),
);
const COMMENT = /\/\*[\s\S]*?\*\//g;
const ROOT_BLOCK = /:root([^{]*)\{([^}]*)\}/g;
const LIGHT_ROOT = /\[data-theme="light"\]\s*$/;
const CUSTOM_PROPERTY = /(--[\w-]+)\s*:\s*([^;]*)/g;

/** Each custom property's value in `theme`: `:root`'s, and the light block's over it. */
function tokenValues(stylesheet: string, theme: ThemeName): Map<string, string> {
  const blocks = [...stylesheet.matchAll(ROOT_BLOCK)].map(([, selector, body]) => ({
    light: LIGHT_ROOT.test(selector ?? ""),
    body: body ?? "",
  }));
  const applying = blocks.filter((block) => !block.light || theme === "light");
  return new Map(
    applying.flatMap(({ body }) =>
      [...body.matchAll(CUSTOM_PROPERTY)].map(
        ([, name, value]) => [name ?? "", value ?? ""] as [string, string],
      ),
    ),
  );
}

/** `stylesheet` as `theme` has it: no comments or `:root` blocks, each `var()`
 * replaced by its value, and any run of white space one space. */
function resolved(stylesheet: string, theme: ThemeName): string {
  const text = stylesheet.replace(COMMENT, "");
  const values = tokenValues(text, theme);
  const replaced = (written: string): string =>
    written.replace(/var\((--[\w-]+)\)/g, (_use, name: string) => {
      const value = values.get(name);
      if (value === undefined) {
        throw new Error(`${name} is used and never defined`);
      }
      return replaced(value);
    });
  return replaced(text.replace(ROOT_BLOCK, "")).replace(/\s+/g, " ").trim();
}

function digest(text: string): string {
  return createHash("sha256").update(text).digest("hex");
}

/** What stands in `stylesheet`'s `:root` blocks but custom properties, and any
 * custom property written outside them: a value replacing cannot account for. */
function outsideTheTokens(stylesheet: string): string[] {
  const text = stylesheet.replace(COMMENT, "");
  const inRoot = [...text.matchAll(ROOT_BLOCK)].flatMap(([, , body]) =>
    (body ?? "")
      .split(";")
      .map((declaration) => declaration.trim())
      .filter((declaration) => declaration !== "" && !declaration.startsWith("--")),
  );
  const elsewhere = [...text.replace(ROOT_BLOCK, "").matchAll(/(?:^|[{;])\s*(--[\w-]+)\s*:/gm)].map(
    ([, name]) => name ?? "",
  );
  return [...inRoot, ...elsewhere];
}

describe("a button that cannot be pressed", () => {
  it.each([".replay-button", ".landing-button", ".ds-button"])("looks so, as %s", (selector) => {
    const rule = new RegExp(`\\${selector}:disabled\\s*\\{([^}]*)\\}`).exec(STYLES)?.[1] ?? "";
    expect(rule).toMatch(/opacity:/);
    expect(rule).toMatch(/cursor:\s*not-allowed/);
  });
});

describe("the stylesheet with its tokens resolved (P19.1)", () => {
  const written = `
    /* What the page is drawn with. */
    :root { --size: 8px; --ink: #111111; --deep: var(--ink); }
    :root[data-theme="light"] { --ink: #eeeeee; }
    .a { padding: var(--size) 12px; color: var(--deep); }
    .b { gap: 4px; }
  `;

  it("is what it was", () => {
    expect(
      {
        dark: digest(resolved(STYLES_OF_THE_PAGES, "dark")),
        light: digest(resolved(STYLES_OF_THE_PAGES, "light")),
      },
      "the stylesheet draws something else: a token step must not; a change of style writes these digests in RESOLVED_DIGESTS",
    ).toEqual(RESOLVED_DIGESTS);
  });

  it("leaves out the rules of no page, and only those", () => {
    expect(STYLES_OF_THE_PAGES).not.toContain(".ds-");
    expect(STYLES_OF_THE_PAGES).toContain(".landing-button");
  });

  it("uses no token that is not defined, in a component's rules too", () => {
    expect(() => resolved(STYLES, "dark")).not.toThrow();
    expect(() => resolved(STYLES, "light")).not.toThrow();
  });

  it("can be replaced by a substitution, as custom properties stand on :root alone", () => {
    expect(outsideTheTokens(STYLES)).toEqual([]);
  });

  it("refuses what a substitution cannot account for", () => {
    expect(
      outsideTheTokens(":root { --a: 1px; color-scheme: dark; } .b { --c: 2px; color: red; }"),
    ).toEqual(["color-scheme: dark", "--c"]);
  });

  it("gives each theme its values, nested ones too", () => {
    expect(resolved(written, "dark")).toBe(
      ".a { padding: 8px 12px; color: #111111; } .b { gap: 4px; }",
    );
    expect(resolved(written, "light")).toBe(
      ".a { padding: 8px 12px; color: #eeeeee; } .b { gap: 4px; }",
    );
  });

  it("does not see a value written as a token, a token's name, comments or white space", () => {
    const same = `
      :root { --space-3: 8px; --gap-small: 4px; --text: #111111; --pad: 12px; }
      :root[data-theme="light"] { --text: #eeeeee; }
      .a {
        padding: var(--space-3) var(--pad);
        /* Its colour. */
        color: var(--text);
      }
      .b { gap: var(--gap-small); }
    `;
    for (const theme of ["dark", "light"] as const) {
      expect(digest(resolved(same, theme))).toBe(digest(resolved(written, theme)));
    }
  });

  it("sees a value moved by the least, in the theme it moved in", () => {
    const original = {
      dark: digest(resolved(written, "dark")),
      light: digest(resolved(written, "light")),
    };
    const pixel = written.replace("--size: 8px", "--size: 9px");
    expect(digest(resolved(pixel, "dark"))).not.toBe(original.dark);
    expect(digest(resolved(pixel, "light"))).not.toBe(original.light);

    const onlyLight = written.replace("--ink: #eeeeee", "--ink: #eeeeef");
    expect(digest(resolved(onlyLight, "dark"))).toBe(original.dark);
    expect(digest(resolved(onlyLight, "light"))).not.toBe(original.light);

    const raw = written.replace("gap: 4px", "gap: 5px");
    expect(digest(resolved(raw, "dark"))).not.toBe(original.dark);
  });

  it("sees two rules change order, which changes the cascade", () => {
    const swapped = `
      :root { --size: 8px; --ink: #111111; --deep: var(--ink); }
      :root[data-theme="light"] { --ink: #eeeeee; }
      .b { gap: 4px; }
      .a { padding: var(--size) 12px; color: var(--deep); }
    `;
    expect(digest(resolved(swapped, "dark"))).not.toBe(digest(resolved(written, "dark")));
  });

  it("refuses a token used and never defined", () => {
    expect(() => resolved(".a { color: var(--gone); }", "dark")).toThrow("--gone");
  });

  it("reads a stylesheet's imports in their place, in order, nested ones too", () => {
    const files: Record<string, string> = {
      "/s/styles.css":
        '@import "./design/tokens.css";\n@import "./pages.css";\n.last { top: 0; }\n',
      "/s/design/tokens.css": '@import "./colours.css";\n:root { --a: 1px; }\n',
      "/s/design/colours.css": ":root { --b: 2px; }\n",
      "/s/pages.css": ".page { gap: var(--a); }\n",
    };
    expect(withImports("/s/styles.css", (path) => files[path] ?? "")).toBe(
      ":root { --b: 2px; }\n\n:root { --a: 1px; }\n\n.page { gap: var(--a); }\n\n.last { top: 0; }\n",
    );
  });
});

// The sizes held (P19.4, P19.5), each with the token its value must name.
const SIZE_SCALES: readonly { property: RegExp; token: RegExp }[] = [
  { property: /^font(?:-size)?$/, token: /^var\(--font-[\w-]+\)$/ },
  { property: /^border(?:-[a-z]+)*-radius$/, token: /^var\(--radius-[\w-]+\)$/ },
  {
    property: /^min-(?:width|height|inline-size|block-size)$/,
    token: /^var\(--target(?:-compact)?\)$/,
  },
  {
    property: /^(?:(?:grid-)?(?:row-|column-)?gap|padding(?:-[a-z-]+)?|margin(?:-[a-z-]+)?)$/,
    token: /^var\(--space-[1-9]\)$/,
  },
  // An outline's shorthand also names its style and a colour, which the colours' guard holds.
  {
    property: /^outline(?:-width|-offset)?$/,
    token: /^(?:var\(--focus-(?:width|offset)\)|solid|var\(--(?:action|text)\))$/,
  },
];
// What is not on a scale by nature: nothing at all, the browser's own, what its
// text gave it, or a share of its box.
const NEEDS_NO_SCALE = /^(?:0|auto|inherit|-?\d*\.?\d+(?:em|%))$/i;

// What stays written as a value, with why, until a visual step (P19.12) moves it
// onto a scale: moving one draws something else, which a neutral step must not.
// A new entry is a finding about the scales, for review to weigh.
const OFF_SCALE: Readonly<Record<string, string>> = {
  ".controls-device { min-width: 64px }": "a column for the device's name; nothing to press",
  ".controls-open kbd { border-radius: 3px }": "a key's cap, smaller than any control",
  ".controls-open kbd { font-size: 11px }": "a key's cap, under the text of its line",
  ".category-legend .swatch { border-radius: 2px }": "a 12 px swatch; QA baselines draw it",
  ".scalar-bar { border-radius: 2px }": "a legend's 12 px bar, on a QA page",
  ".debug-label { border-radius: 3px }": "a label over the scene; QA baselines draw it",
  ".climate-schedule-bar span.daily { border-radius: 1px }": "an 8 px marker, meant to look square",
  ".panel-stripe { font-size: 10px }": "the mark on a stripe 14 px wide",
  ".landing-combobox .landing-input { min-height: 48px }": "the landing's search, above the target",
  ".landing-dialog { border-radius: 14px }": "the runs dialog, a step above a card's 12",
  ".replay-play { min-width: 52px }": "the transport's main button, wider than its neighbours",
  ".replay-track { border-radius: 7px }": "half the height of the 14 px band it holds",
  ".replay-computed { border-radius: 7px 0 0 7px }": "the rounded end of that 14 px band",
  '.landing-option[aria-selected="true"] { outline: 2px solid var(--action) }':
    "the chosen option's mark, not a focus ring",
  '.landing-option[aria-selected="true"] { outline-offset: -2px }':
    "that mark, inside the option's edge",
  // Spacing between two steps of the scale (P19.5).
  ".panel-card { margin: 10px 0 var(--space-2) }": "room above a card for the title on its outline",
  ".seen-in-the-view dd { margin: 0 0 var(--space-2) 18px }": "a note under its glyph's words",
  ".field-views { gap: 10px }": "between a field's slices, in a panel's width",
  ".camera-entities { padding-left: 20px }": "a list's indent",
  ".plant-structure ul { padding-left: 14px }": "a tree's indent, per level",
  ".move-list { padding-left: 18px }": "a list's indent",
  ".builder-findings ul { padding-left: 18px }": "a list's indent",
  ".landing-card { gap: 10px }": "between a card's lines",
  ".landing-link-button { padding: 0 18px }": "a family of button's sides, of the two it has",
  ".landing-button { padding: 0 18px }": "a family of button's sides, of the two it has",
  ".landing-combobox .landing-input { padding: 0 14px }": "the search's sides, as its options'",
  ".landing-option { padding: var(--space-4) 14px }": "an option's sides, as the search's",
  ".landing-option-none { padding: var(--space-5) 14px }": "the note for no option, as an option's",
  ".landing-run { padding: var(--space-5) 20px }": "a run's row, to the dialog's edge",
  ".landing-status { padding: var(--space-1) 10px }": "a status chip's sides",
  ".landing-dialog-head { padding: 20px var(--space-7) var(--space-5) }": "the dialog's first line",
  '.landing-dialog p[role="alert"], .landing-dialog p[role="status"] { padding: 10px var(--space-7) }':
    "a message's line in the dialog",
  ".replay-header { gap: var(--space-4) 14px }": "between the header's items",
  ".replay-header { padding: 10px 20px }": "the header's edge",
  ".replay-transport { padding: 14px 20px var(--space-6) }":
    "the transport's edge, as the header's",
  ".replay-controls { gap: 10px 20px }": "between the transport's groups",
  ".replay-refused { margin: 0 0 10px }": "a refusal, over the controls",
  ".replay-pace select { padding: 0 10px }": "the select's sides, in a 44 px control",
};
// What no spacing scale should hold: a hairline, and an offset that centres a mark
// of a given width on its place, which follows from that width.
const HAIRLINES_AND_OFFSETS: Readonly<Record<string, string>> = {
  ".visually-hidden { margin: -1px }": "takes the 1 px box out of the flow",
  ".debug-label { padding: 1px var(--space-2) }": "a label's hairline above and below",
  ".climate-schedule-bar span { margin-left: -4px }": "half the 8 px marker",
  ".replay-frontier { margin-left: -1px }": "half the 2 px line",
  ".replay-handle { margin-left: -10px }": "half the 20 px handle",
};
// Not pixels: a chart's geometry, which grows with its drawing.
const IN_A_VIEWBOX: Readonly<Record<string, string>> = {
  ".wind-compass-north { font-size: 8px }": "the compass's N, in its viewBox's units",
};

/** Each declaration in `stylesheet`, outside the tokens' `:root` blocks, that
 * sets a held size to anything but its scale's token, as `selector { property:
 * value }`. A value counts as a whole: a raw size in a `calc()` or a `var()`'s
 * fallback is still raw. */
function sizesOffTheScales(stylesheet: string): string[] {
  const rules = stylesheet.replace(COMMENT, "").replace(ROOT_BLOCK, "");
  return [...rules.matchAll(/([^{};]*)\{([^{}]*)\}/g)].flatMap(([, prelude, body]) => {
    const selector = (prelude ?? "").trim().replace(/\s+/g, " ");
    return [...(body ?? "").matchAll(/(?:^|;)\s*([a-z-]+)\s*:\s*([^;]*)/gi)].flatMap(
      ([, name, written]) => {
        const property = (name ?? "").toLowerCase();
        const value = (written ?? "").trim();
        const scale = SIZE_SCALES.find((each) => each.property.test(property));
        const held =
          scale === undefined ||
          value.split(/\s+/).every((word) => NEEDS_NO_SCALE.test(word) || scale.token.test(word));
        return held ? [] : [`${selector} { ${property}: ${value} }`];
      },
    );
  });
}

/** What `found` holds that `listed` does not name, and what `listed` names that
 * is no longer found: each entry answers for one declaration. */
function againstTheList(
  found: readonly string[],
  listed: readonly string[],
): { unlisted: string[]; gone: string[] } {
  const gone = [...listed];
  const unlisted = found.filter((declaration) => {
    const entry = gone.indexOf(declaration);
    if (entry === -1) {
      return true;
    }
    gone.splice(entry, 1);
    return false;
  });
  return { unlisted, gone };
}

describe("the stylesheet's sizes (P19.4, P19.5)", () => {
  it("are their scale's tokens, or named here with why", () => {
    expect(
      againstTheList(sizesOffTheScales(STYLES), [
        ...Object.keys(OFF_SCALE),
        ...Object.keys(IN_A_VIEWBOX),
        ...Object.keys(HAIRLINES_AND_OFFSETS),
      ]),
    ).toEqual({ unlisted: [], gone: [] });
  });

  it("refuse a raw size wherever it is written, and however", () => {
    const written = `
      .a { font-size: 13px; border-radius: 6px; min-height: 44px; min-width: 44px; }
      .b { font: 13px/1.4 system-ui; border-top-left-radius: 6px; }
      .c { border-radius: 7px 0 0 7px; font-size: 1rem; FONT-SIZE: 13PX; }
      .d { font-size: 13px !important; font-size: small; min-block-size: 44px; }
      .e { min-height: calc(var(--target) - 2px); border-radius: var(--radius-md, 6px); }
      @media (min-width: 600px) { .f, .g > .h { min-height: 48px; } }
    `;
    expect(sizesOffTheScales(written)).toEqual([
      ".a { font-size: 13px }",
      ".a { border-radius: 6px }",
      ".a { min-height: 44px }",
      ".a { min-width: 44px }",
      ".b { font: 13px/1.4 system-ui }",
      ".b { border-top-left-radius: 6px }",
      ".c { border-radius: 7px 0 0 7px }",
      ".c { font-size: 1rem }",
      ".c { font-size: 13PX }",
      ".d { font-size: 13px !important }",
      ".d { font-size: small }",
      ".d { min-block-size: 44px }",
      ".e { min-height: calc(var(--target) - 2px) }",
      ".e { border-radius: var(--radius-md, 6px) }",
      ".f, .g > .h { min-height: 48px }",
    ]);
  });

  it("refuse a raw spacing, in any of its properties, and one value raw among tokens", () => {
    const written = `
      .a { gap: 8px; row-gap: 4px; column-gap: 4px; grid-gap: 4px; }
      .b { padding: 8px; padding-left: 8px; padding-inline: 8px; }
      .c { margin: 8px; margin-top: -8px; margin-block-end: 8px; }
      .d { padding: var(--space-4) 10px; margin: 0 0 var(--space-2) 18px; gap: 1px; }
      .e { padding: calc(var(--space-4) + 1px); margin: var(--space-4, 8px); gap: 1rem; }
      .f { outline: 3px solid var(--action); outline-offset: 2px; outline-width: 3px; }
      .g { outline: none; outline: var(--space-1) solid var(--text); }
    `;
    expect(sizesOffTheScales(written)).toEqual([
      ".a { gap: 8px }",
      ".a { row-gap: 4px }",
      ".a { column-gap: 4px }",
      ".a { grid-gap: 4px }",
      ".b { padding: 8px }",
      ".b { padding-left: 8px }",
      ".b { padding-inline: 8px }",
      ".c { margin: 8px }",
      ".c { margin-top: -8px }",
      ".c { margin-block-end: 8px }",
      ".d { padding: var(--space-4) 10px }",
      ".d { margin: 0 0 var(--space-2) 18px }",
      ".d { gap: 1px }",
      ".e { padding: calc(var(--space-4) + 1px) }",
      ".e { margin: var(--space-4, 8px) }",
      ".e { gap: 1rem }",
      ".f { outline: 3px solid var(--action) }",
      ".f { outline-offset: 2px }",
      ".f { outline-width: 3px }",
      ".g { outline: none }",
      ".g { outline: var(--space-1) solid var(--text) }",
    ]);
  });

  it("refuse a token of another scale", () => {
    const written = `
      .a { font-size: var(--radius-md); border-radius: var(--font-sm); }
      .b { min-height: var(--font-sm); padding: var(--radius-md); gap: var(--target); }
      .c { font-size: var(--space-4); margin: var(--font-sm); }
    `;
    expect(sizesOffTheScales(written)).toEqual([
      ".a { font-size: var(--radius-md) }",
      ".a { border-radius: var(--font-sm) }",
      ".b { min-height: var(--font-sm) }",
      ".b { padding: var(--radius-md) }",
      ".b { gap: var(--target) }",
      ".c { font-size: var(--space-4) }",
      ".c { margin: var(--font-sm) }",
    ]);
  });

  it("let through a token, what follows its text or its box, and what they do not hold", () => {
    const written = `
      /* .gone { font-size: 13px; } */
      :root { --font-sm: 13px; --radius-md: 6px; }
      .a { font-size: var(--font-sm); border-radius: var(--radius-md) 0 0 var(--radius-md); }
      .b { font: inherit; font-size: inherit; min-height: var(--target); min-width: 0; }
      .c { font-size: 0.7em; min-height: 1.4em; border-radius: 50%; min-width: 100%; }
      .d { height: 44px; width: 13px; top: 44px; font-weight: 600; border: 2px solid; }
      .f { gap: var(--space-3) var(--space-4); padding: 0 var(--space-5); margin: 0 auto; }
      .g { padding-left: 1.5em; margin-top: -0.75em; margin-left: 50%; gap: 0; }
      .h { outline: var(--focus-width) solid var(--action); outline-offset: var(--focus-offset); }
      .e::after { content: ""; }
    `;
    expect(sizesOffTheScales(written)).toEqual([]);
  });

  it("refuse what the list does not name, and a name no longer found", () => {
    expect(
      againstTheList(
        [".a { font-size: 11px }", ".new { font-size: 11px }"],
        [".a { font-size: 11px }", ".moved { font-size: 10px }"],
      ),
    ).toEqual({ unlisted: [".new { font-size: 11px }"], gone: [".moved { font-size: 10px }"] });
  });

  it("let one name answer for one declaration, not for every copy of it", () => {
    expect(
      againstTheList(
        [".a { font-size: 11px }", ".a { font-size: 11px }"],
        [".a { font-size: 11px }"],
      ),
    ).toEqual({ unlisted: [".a { font-size: 11px }"], gone: [] });
  });
});

/** Each rule's selector list in a stylesheet, its comments left out and its quotes kept. */
function selectorLists(stylesheet: string): string[] {
  return [...stylesheet.replace(COMMENT, "").matchAll(/([^{};]*)\{/g)].map(([, prelude]) =>
    (prelude ?? "").trim().replace(/\s+/g, " "),
  );
}

/** The selectors in `stylesheets` that name a component outside `src/design/`. */
function componentsRestyled(stylesheets: readonly { path: string; text: string }[]): string[] {
  return stylesheets
    .filter(({ path }) => !path.includes("/src/design/"))
    .flatMap(({ text }) => selectorLists(text).filter((list) => /(?<![\w-])ds-/.test(list)));
}

// The focus rings written today. One ring on every control, in `base.css`, is a visual
// step (P19.12), which takes these with it: this can only shrink.
const FOCUS_RINGS = [
  ".ds-button:focus-visible",
  ".home-button:focus-visible",
  ".panel-stripe:hover, .panel-stripe:focus-visible",
  ".replay-handle:focus-visible",
];

describe("the design system's components (P19.6)", () => {
  it("are styled in src/design/ alone, so that no page restyles one", () => {
    const stylesheets = importedStylesheets(ENTRY);
    expect(stylesheets.map(({ path }) => path).filter((path) => path.includes("/design/"))).toEqual(
      [
        expect.stringMatching(/tokens/),
        expect.stringMatching(/base/),
        expect.stringMatching(/components/),
      ],
    );
    expect(componentsRestyled(stylesheets)).toEqual([]);
  });

  it("refuse a page's rule that names one, however it is selected", () => {
    const written = `
      /* .ds-button in a comment. */
      .bands-chart, .cards-ds-row { gap: 0; }
      .landing .ds-button { color: red; }
      .ds-icon-button:hover { opacity: 1; }
      [class*="ds-button"] { opacity: 1; }
      @media (min-width: 600px) { .a > .ds-page { color: red; } }
    `;
    expect(
      componentsRestyled([
        { path: "/web/src/landing/landing.css", text: written },
        { path: "/web/src/design/components.css", text: ".ds-button { gap: 0; }" },
      ]),
    ).toEqual([
      ".landing .ds-button",
      ".ds-icon-button:hover",
      '[class*="ds-button"]',
      ".a > .ds-page",
    ]);
  });

  it("are read through the entry's imports, nested ones too", () => {
    const files: Record<string, string> = {
      "/s/styles.css": '@import "./design/tokens.css";\n.a { gap: 0; }\n',
      "/s/design/tokens.css": '@import "./colours.css";\n',
      "/s/design/colours.css": ":root { --b: 2px; }\n",
    };
    expect(
      importedStylesheets("/s/styles.css", (path) => files[path] ?? "").map(({ path }) => path),
    ).toEqual(["/s/styles.css", "/s/design/tokens.css", "/s/design/colours.css"]);
  });

  it("wear one focus ring of the tokens' sizes", () => {
    const rule = /\.ds-button:focus-visible\s*\{([^}]*)\}/.exec(STYLES)?.[1] ?? "";
    expect(rule).toMatch(/outline:\s*var\(--focus-width\) solid var\(--action\)/);
    expect(rule).toMatch(/outline-offset:\s*var\(--focus-offset\)/);
  });
});

/** The rules in `stylesheet` that draw a focus ring of their own. */
function focusRings(stylesheet: string): string[] {
  return selectorLists(stylesheet).filter((list) => list.includes(":focus-visible"));
}

describe("the stylesheet's focus rings (P19.6)", () => {
  it("are the ones named here", () => {
    expect(againstTheList(focusRings(STYLES), FOCUS_RINGS)).toEqual({ unlisted: [], gone: [] });
  });

  it("refuse one more, whatever its selector", () => {
    expect(
      focusRings(
        ".a:focus-visible { gap: 0; } .b:focus { gap: 0; } :is(.c, .d:focus-visible) { gap: 0; }",
      ),
    ).toEqual([".a:focus-visible", ":is(.c, .d:focus-visible)"]);
  });
});

// Each page's rules stand in its own stylesheet, beside its sources (P19.9): its
// classes there alone, and no other's there.
const PAGE_STYLESHEETS: Readonly<Record<string, string>> = {
  builder: "/src/builder/builder.css",
};

/** The selector lists in `stylesheets` that name a page's class outside its own
 * stylesheet, or, in a page's stylesheet, a class of something else. */
function pageRulesMisplaced(stylesheets: readonly { path: string; text: string }[]): string[] {
  return stylesheets.flatMap(({ path, text }) => {
    const page = Object.keys(PAGE_STYLESHEETS).find((word) =>
      path.endsWith(PAGE_STYLESHEETS[word] ?? ""),
    );
    return selectorLists(text).filter((list) => {
      if (list.startsWith("@")) {
        return false;
      }
      const words = [...list.matchAll(/\.(-?[_a-zA-Z][\w-]*)/g)].map(
        ([, name]) => (name ?? "").split("-")[0] ?? "",
      );
      return page === undefined
        ? words.some((word) => word in PAGE_STYLESHEETS)
        : words.some((word) => word !== page);
    });
  });
}

describe("a page's stylesheet (P19.9)", () => {
  it("holds its rules, and only its own", () => {
    const stylesheets = importedStylesheets(ENTRY);
    for (const file of Object.values(PAGE_STYLESHEETS)) {
      expect(stylesheets.map(({ path }) => path)).toContainEqual(expect.stringContaining(file));
    }
    expect(pageRulesMisplaced(stylesheets)).toEqual([]);
  });

  it("refuses a page's rule written elsewhere, and another's written in it", () => {
    expect(
      pageRulesMisplaced([
        {
          path: "/web/src/styles.css",
          text: ".builder-side h1 { gap: 0; } .info-panel, .builder { gap: 0; } .panel { gap: 0; }",
        },
        {
          path: "/web/src/builder/builder.css",
          text: "@media (max-width: 840px) { .builder { gap: 0; } } .builder .hud { gap: 0; }",
        },
      ]),
    ).toEqual([".builder-side h1", ".info-panel, .builder", ".builder .hud"]);
  });
});
