import { readFileSync } from "node:fs";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { buildInfo } from "./buildInfo";
import { InfoPanel } from "./InfoPanel";

const LOADING = { status: "loading" } as const;
const REFERENCE = { kind: "reference" } as const;
const NONE = { status: "none" } as const;
const ignore = () => undefined;

describe("the viewer's information panel", () => {
  it("identifies the viewer", () => {
    const html = renderToStaticMarkup(
      <InfoPanel
        build={buildInfo}
        scenarios={LOADING}
        source={REFERENCE}
        scene={NONE}
        onSource={ignore}
      />,
    );

    expect(html).toContain("<h1>greenhouse-sim viewer</h1>");
  });

  it("shows the build metadata it was given", () => {
    const html = renderToStaticMarkup(
      <InfoPanel
        build={{ simulatorVersion: "9.8.7", sourceCommit: "abc1234" }}
        scenarios={LOADING}
        source={REFERENCE}
        scene={NONE}
        onSource={ignore}
      />,
    );

    // In one line, at the panel's end, under everything it holds (#206),
    // with the panels' theme beside it when it can be changed (#208).
    expect(html).toContain("simulator 9.8.7 · commit abc1234</p></div></aside>");
  });

  it("reports the version of the simulator it ships with", () => {
    const pyproject = readFileSync(new URL("../../pyproject.toml", import.meta.url), "utf8");

    expect(pyproject).toContain(`version = "${buildInfo.simulatorVersion}"`);
  });
});
