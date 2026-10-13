import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { RunManifest } from "./manifest";
import { QaPanel } from "./QaPanel";
import type { RunState } from "./state";

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

// Noon on the reference greenhouse's second day, as the simulator holds it.
const START = "2026-02-28T23:00:00Z";
const FRAME = {
  frame_id: "f",
  sensor_id: "path_camera",
  timestamp: "2026-03-02T11:00:00Z",
  pose: { x_m: 0, y_m: 0, z_m: 0, qw: 1, qx: 0, qy: 0, qz: 0 },
  intrinsics: { width: 640, height: 480, fx: 457, fy: 457 },
  modalities: ["RGB", "DEPTH"],
};
const STATE: RunState = {
  runId: "reference_greenhouse-climate-c562c827",
  start: START,
  at: "2026-03-02T11:00:00Z",
  timeS: 129_600,
  day: 1,
  houseAir: { temperatureC: 20.3484, humidityPct: 32.3431, co2Ppm: 420 },
  cropModel: "organ",
  plants: 32,
  daysLived: 1,
  levels: { heater: 0, roof_vent_1: 0.5 },
  commandsGiven: 2,
  latestCommands: [
    { timeS: 118_800, actuatorId: "heater", level: 0 },
    { timeS: 118_800, actuatorId: "roof_vent_1", level: 0.5 },
  ],
  sensors: [
    {
      sensor_id: "temperature_back",
      state: "stale",
      due_at: "2026-03-02T10:59:00Z",
      latest_at: "2026-03-02T10:58:00Z",
    },
  ],
  cameras: [{ sensorId: "path_camera", frames: 1441, latest: FRAME }],
};

describe("QA mode's panel", () => {
  it("lists what the run is made from, and the simulator's and the viewer's versions", () => {
    const html = renderToStaticMarkup(
      <QaPanel
        build={BUILD}
        served={{ status: "loaded", served: { version: "0.1.0", commit: "c1964e9" } }}
        manifest={{ status: "loaded", manifest: MANIFEST }}
        state={{ status: "none" }}
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
        state={{ status: "none" }}
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
        state={{ status: "none" }}
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
        state={{ status: "unavailable", reason: "the simulator API answered 400" }}
      />,
    );

    expect(html).toContain(
      'data-testid="manifest-simulator">cannot be read: the simulator API answered 500<',
    );
    expect(html).toContain(
      "The run&#x27;s manifest cannot be read: the simulator API answered 404.",
    );
    expect(html).toContain("What the run holds cannot be read: the simulator API answered 400.");
  });

  it("says what each process of the run holds at its moment, a stale sensor marked", () => {
    const html = renderToStaticMarkup(
      <QaPanel
        build={BUILD}
        served={{ status: "loading" }}
        manifest={{ status: "loading" }}
        state={{ status: "loaded", state: STATE }}
      />,
    );

    expect(html).toContain(
      'data-testid="developer-clock">day 1, 12 h 00 min (2026-03-02 11:00 UTC), run reference_greenhouse-climate-c562c827<',
    );
    expect(html).toContain('data-testid="developer-house-air">20.35 °C, 32.34%, 420 ppm<');
    expect(html).toContain(
      'data-testid="developer-crop">32 plants, organ by organ; last plant day 0<',
    );
    expect(html).toContain('data-testid="developer-levels">heater 0%, roof_vent_1 50%<');
    expect(html).toContain("2 given, the latest:");
    expect(html).toContain("<li>day 1, 9 h 00 min: roof_vent_1 50%</li>");
    expect(html).toContain(
      '<li class="stale">temperature_back: stale, latest day 1, 11 h 58 min</li>',
    );
    expect(html).toContain("<li>path_camera: 1441 frames, latest day 1, 12 h 00 min</li>");
    // The developer's list comes before the run's manifest.
    expect(html.indexOf("Developer")).toBeLessThan(html.indexOf("Run manifest"));
  });
});
