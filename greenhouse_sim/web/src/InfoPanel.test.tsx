import { readFileSync } from "node:fs";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { buildInfo } from "./buildInfo";
import { InfoPanel } from "./InfoPanel";

const LOADING = { status: "loading" } as const;

describe("the viewer's information panel", () => {
  it("identifies the viewer", () => {
    const html = renderToStaticMarkup(<InfoPanel build={buildInfo} scenarios={LOADING} />);

    expect(html).toContain("<h1>greenhouse-sim viewer</h1>");
  });

  it("shows the build metadata it was given", () => {
    const html = renderToStaticMarkup(
      <InfoPanel
        build={{ simulatorVersion: "9.8.7", sourceCommit: "abc1234" }}
        scenarios={LOADING}
      />,
    );

    expect(html).toContain("<dd>9.8.7</dd>");
    expect(html).toContain("<dd>abc1234</dd>");
  });

  it("reports the version of the simulator it ships with", () => {
    const pyproject = readFileSync(new URL("../../pyproject.toml", import.meta.url), "utf8");

    expect(pyproject).toContain(`version = "${buildInfo.simulatorVersion}"`);
  });
});
