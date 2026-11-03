import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

describe("the page every address is served", () => {
  it("names an icon, so that a browser does not ask for a /favicon.ico there is not", () => {
    const page = readFileSync(join(process.cwd(), "index.html"), "utf8");

    expect(page).toMatch(/<link rel="icon" href="[^"]+"/);
  });
});
