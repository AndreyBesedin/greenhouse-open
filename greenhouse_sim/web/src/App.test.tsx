import { readFileSync } from "node:fs";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { App } from "./App";
import { buildInfo } from "./buildInfo";

describe("the viewer's bootstrap page", () => {
  it("identifies itself as the greenhouse-sim viewer", () => {
    const html = renderToStaticMarkup(<App />);

    expect(html).toContain("<h1>greenhouse-sim viewer</h1>");
  });

  it("shows the build metadata it was given", () => {
    const html = renderToStaticMarkup(
      <App build={{ simulatorVersion: "9.8.7", sourceCommit: "abc1234" }} />,
    );

    expect(html).toContain("<dd>9.8.7</dd>");
    expect(html).toContain("<dd>abc1234</dd>");
  });

  it("reports the version of the simulator it ships with", () => {
    const pyproject = readFileSync(new URL("../../pyproject.toml", import.meta.url), "utf8");

    expect(pyproject).toContain(`version = "${buildInfo.simulatorVersion}"`);
  });
});
