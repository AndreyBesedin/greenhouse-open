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

const STYLES = withImports(fileURLToPath(new URL("./styles.css", import.meta.url)));
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
  /^--(?:font-(?:xs|sm|md|lg|xl|[234]xl)|radius-(?:sm|md|lg|xl|pill)|space-[1-9]|focus-(?:width|offset)|target)$/;

function misnamedTokens(names: Iterable<string>): string[] {
  return [...names].filter((name) => !COLOUR_ROLE.test(name) && !SIZE_STEP.test(name));
}

describe("the stylesheet", () => {
  it("colours every panel's text and background from the panels' theme (#208)", () => {
    expect(unthemed(STYLES)).toEqual([]);
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
// prints here, in its own diff, where review sees them; a token step must not.
// It goes when selectors start to move (P19.6), and the page baselines hold.
const RESOLVED_DIGESTS = {
  dark: "6f0022338f831cb03b26d19ea245bfea680c7a9627e3882c49e12b913cfe93ea",
  light: "d1738881af60720ad7c4b032078aa8a70592133e3aecb6d76c6a4c023a400237",
};
type ThemeName = keyof typeof RESOLVED_DIGESTS;
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
  it.each([".replay-button", ".landing-button"])("looks so, as %s", (selector) => {
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
      { dark: digest(resolved(STYLES, "dark")), light: digest(resolved(STYLES, "light")) },
      "the stylesheet draws something else: a token step must not; a change of style writes these digests in RESOLVED_DIGESTS",
    ).toEqual(RESOLVED_DIGESTS);
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
  { property: /^min-(?:width|height|inline-size|block-size)$/, token: /^var\(--target\)$/ },
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
