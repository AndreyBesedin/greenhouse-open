// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { afterEach, describe, expect, it, vi } from "vitest";

import { storedTheme } from "./design/theme";

const PAGE = readFileSync(join(process.cwd(), "index.html"), "utf8");

/** The page's own scripts, those written in it rather than loaded. */
function inlineScripts(page: string): string[] {
  return [...page.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(([, body]) => body ?? "");
}

/** The theme the page's head puts on the document, run as a browser runs it. */
function themeBeforeTheScripts(): string | undefined {
  delete document.documentElement.dataset.theme;
  for (const script of inlineScripts(PAGE)) {
    new Function(script)();
  }
  return document.documentElement.dataset.theme;
}

describe("the page every address is served", () => {
  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
    delete document.documentElement.dataset.theme;
  });

  it("names an icon, so that a browser does not ask for a /favicon.ico there is not", () => {
    expect(PAGE).toMatch(/<link rel="icon" href="[^"]+"/);
  });

  it("puts the theme on the document in its head, before the viewer's scripts", () => {
    const head = PAGE.slice(0, PAGE.indexOf("</head>"));
    expect(inlineScripts(head)).toHaveLength(1);
    expect(PAGE.indexOf("<script>")).toBeLessThan(PAGE.indexOf('<script type="module"'));
  });

  it("puts on the document the theme chosen, as the viewer reads it", () => {
    expect(themeBeforeTheScripts()).toBe("dark");

    localStorage.setItem("greenhouse-sim.panels", "light");
    // The key the viewer keeps its choice under, which the page reads too.
    expect(storedTheme()).toBe("light");
    expect(themeBeforeTheScripts()).toBe("light");

    localStorage.setItem("greenhouse-sim.panels", "pink");
    expect(themeBeforeTheScripts()).toBe(storedTheme());
  });

  it("is dark when the browser keeps nothing it can read", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("refused");
    });
    expect(themeBeforeTheScripts()).toBe("dark");
    expect(storedTheme()).toBe("dark");
  });
});
