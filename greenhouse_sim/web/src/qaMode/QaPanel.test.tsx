import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { RunManifest } from "./manifest";
import { QaPanel } from "./QaPanel";

const BUILD = { simulatorVersion: "0.1.0", sourceCommit: "c1964e9" };
// The reference greenhouse's run.
const MANIFEST: RunManifest = {
  scenarioId: "reference_greenhouse",
  format: 1,
  version: "5a7c1ee05a34bf3c",
  seed: 42,
  startDate: "2026-03-01",
  days: 120,
  openingDay: 80,
  cropModel: "organ",
  variety: "cherry_tomato",
  airflow: "uniform",
  weather: "default",
  weatherKind: "synthetic",
  cloudCoverPct: null,
  windFromDeg: null,
};

describe("QA mode's panel", () => {
  it("lists what the run is made from, and the simulator's and the viewer's versions", () => {
    const html = renderToStaticMarkup(
      <QaPanel
        build={BUILD}
        served={{ status: "loaded", served: { version: "0.1.0", commit: "c1964e9" } }}
        manifest={{ status: "loaded", manifest: MANIFEST }}
      />,
    );

    expect(html).toContain('aria-label="QA mode"');
    expect(html).toContain(
      'data-testid="manifest-scenario">reference_greenhouse, version 5a7c1ee05a34bf3c, format 1<',
    );
    expect(html).toContain('data-testid="manifest-seed">42<');
    expect(html).toContain('data-testid="manifest-weather">its own, synthetic<');
    expect(html).toContain('data-testid="manifest-simulator">0.1.0, commit c1964e9<');
    expect(html).toContain('data-testid="manifest-viewer">0.1.0, commit c1964e9<');
    expect(html).not.toContain("manifest-commits-differ");
  });

  it("warns when the viewer was built from another commit than the simulator runs", () => {
    const html = renderToStaticMarkup(
      <QaPanel
        build={BUILD}
        served={{ status: "loaded", served: { version: "0.1.0", commit: "0a1b2c3" } }}
        manifest={{ status: "none" }}
      />,
    );

    expect(html).toContain('data-testid="manifest-commits-differ"');
    // Another scene than a scenario's has no manifest: only the versions.
    expect(html).not.toContain("manifest-seed");
  });

  it("does not warn when a commit is unknown, as an installed simulator's is", () => {
    const html = renderToStaticMarkup(
      <QaPanel
        build={BUILD}
        served={{ status: "loaded", served: { version: "0.1.0", commit: "unknown" } }}
        manifest={{ status: "none" }}
      />,
    );

    expect(html).toContain('data-testid="manifest-simulator">0.1.0, commit unknown<');
    expect(html).not.toContain("manifest-commits-differ");
  });

  it("says when the simulator or the manifest cannot be read", () => {
    const html = renderToStaticMarkup(
      <QaPanel
        build={BUILD}
        served={{ status: "unavailable", reason: "the simulator API answered 500" }}
        manifest={{ status: "unavailable", reason: "the simulator API answered 404" }}
      />,
    );

    expect(html).toContain(
      'data-testid="manifest-simulator">cannot be read: the simulator API answered 500<',
    );
    expect(html).toContain(
      "The run&#x27;s manifest cannot be read: the simulator API answered 404.",
    );
  });
});
