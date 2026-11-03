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

function misnamedTokens(names: Iterable<string>): string[] {
  return [...names].filter((name) => !COLOUR_ROLE.test(name));
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

  it("names each colour for what it does, not where it stands (P19.3)", () => {
    expect(misnamedTokens(tokenValues(STYLES, "dark").keys())).toEqual([]);
  });

  it("refuses a token named for a place", () => {
    expect(misnamedTokens(["--text-soft", "--panel-text", "--landing-bg", "--textual"])).toEqual([
      "--panel-text",
      "--landing-bg",
      "--textual",
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
  dark: "3c34a059cf8aea9e5ce5b759912b6ab4d44e377ae579eb4ced022e6576762ccb",
  light: "680c2d0e9826251b941e1d9f1113de9307304e580a5557144f4e67ebcfed3f73",
};
type ThemeName = keyof typeof RESOLVED_DIGESTS;
const COMMENT = /\/\*[\s\S]*?\*\//g;
const ROOT_BLOCK = /:root([^{]*)\{([^}]*)\}/g;
const LIGHT_ROOT = /="light"\]\s*$/;
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
      :root[data-panels="light"] { --text: #eeeeee; }
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
