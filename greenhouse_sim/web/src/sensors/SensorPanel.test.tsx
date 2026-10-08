import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { CameraFrames } from "./CameraFrames";
import { loadSensorReadings, type SensorReadings, sensorsUrl } from "./readings";
import { SensorPanel } from "./SensorPanel";

const START = "2026-01-01T00:00:00Z";
const READINGS: SensorReadings = {
  runId: "climate_box-climate-0",
  start: START,
  observations: [
    { sensor_id: "t", observation_type: "air_temperature_c", timestamp: START, value: 16 },
    {
      sensor_id: "t",
      observation_type: "air_temperature_c",
      timestamp: "2026-01-01T00:10:00Z",
      value: 14.9611,
    },
    {
      sensor_id: "rh",
      observation_type: "relative_humidity_pct",
      timestamp: START,
      value: 100,
      quality: ["CLIPPED"],
    },
  ],
  freshness: [
    {
      sensor_id: "t",
      due_at: "2026-01-01T00:10:00Z",
      latest_at: "2026-01-01T00:10:00Z",
      stale: false,
    },
    { sensor_id: "rh", due_at: "2026-01-01T00:10:00Z", latest_at: START, stale: true },
    { sensor_id: "co2", due_at: null, latest_at: null, stale: false },
  ],
  frames: [0, 1].map((minute) => ({
    frame_id: `sim_camera_20260101T000${minute}00Z_frame`,
    sensor_id: "camera",
    timestamp: `2026-01-01T00:0${minute}:00Z`,
    position: { x: 0.6, y: 3.2, z: 2.2 },
    target: { x: 11, y: 3.2, z: 0.6 },
    intrinsics: { width: 640, height: 480, fx: 457.007, fy: 457.007 },
    modalities: ["RGB", "DEPTH"],
  })),
  truths: [
    {
      sensor_id: "t",
      observation_type: "air_temperature_c",
      unit: "°C",
      times_s: [0, 600],
      values: [16, 14.9611],
    },
    {
      sensor_id: "par",
      observation_type: "par_umol_m2_s",
      unit: "µmol/m²/s",
      times_s: [0, 600],
      values: [null, null],
    },
  ],
};

describe("a selected sensor", () => {
  it("is read as the climate is asked for, up to the moment drawn", () => {
    expect(
      sensorsUrl("climate_box", "truth", {
        levels: { heater: 1 },
        schedule: [{ timeS: 300, actuatorId: "heater", level: 0 }],
        time: 600,
      }),
    ).toBe("/api/scenarios/climate_box/climate/truth?set=heater:1&schedule=300:heater:0&t=600");
    expect(sensorsUrl("climate_box", "observations", {})).toBe(
      "/api/scenarios/climate_box/climate/observations",
    );
    // As clean sensors would have read, for QA: the truth is the same.
    expect(sensorsUrl("climate_box", "observations", { clean: true })).toBe(
      "/api/scenarios/climate_box/climate/observations?clean=1",
    );
    expect(sensorsUrl("climate_box", "truth", { clean: true })).toBe(
      "/api/scenarios/climate_box/climate/truth",
    );
  });

  it("shows its latest reading, and the truth beside it, for QA", () => {
    const html = renderToStaticMarkup(
      <SensorPanel
        sensorId="t"
        unit="°C"
        state={{ status: "loaded", readings: READINGS }}
        until={600}
        imperfect={true}
        onImperfect={() => undefined}
      />,
    );

    expect(html).toContain('data-testid="sensor-reading">14.96 °C at 10 min<');
    expect(html).toContain('aria-label="Truth, for QA only"');
    expect(html).toContain('data-testid="sensor-truth">14.96 °C at 10 min<');
    // Its readings as dots against the truth's line, and the QA switch.
    expect(html.match(/<circle/g)).toHaveLength(2);
    expect(html).toContain('class="sensor-chart-truth"');
    expect(html).toContain('<input type="checkbox" checked=""/> Imperfections');
  });

  it("says when nothing gives its quantity", () => {
    const html = renderToStaticMarkup(
      <SensorPanel
        sensorId="par"
        unit="µmol/m²/s"
        state={{ status: "loaded", readings: READINGS }}
        until={600}
        imperfect={true}
        onImperfect={() => undefined}
      />,
    );

    expect(html).toContain("No reading: nothing gives this quantity yet.");
    expect(html).toContain('data-testid="sensor-truth">none<');
  });

  it("says whether its latest reading due has come", () => {
    const panel = (sensorId: string) =>
      renderToStaticMarkup(
        <SensorPanel
          sensorId={sensorId}
          unit="%"
          state={{ status: "loaded", readings: READINGS }}
          until={600}
          imperfect={true}
          onImperfect={() => undefined}
        />,
      );

    expect(panel("t")).toContain(
      'data-testid="sensor-freshness">Fresh: its reading of 10 min has come.<',
    );
    expect(panel("rh")).toContain(
      'class="stale" data-testid="sensor-freshness">Stale: its reading of 10 min, due by now, has not come.<',
    );
    expect(panel("co2")).toContain("Its first reading is not due yet.");
  });

  it("says when its reading was held at its instrument's range", () => {
    const html = renderToStaticMarkup(
      <SensorPanel
        sensorId="rh"
        unit="%"
        state={{ status: "loaded", readings: READINGS }}
        until={600}
        imperfect={true}
        onImperfect={() => undefined}
      />,
    );

    expect(html).toContain("100 % at 0 min, clipped at its instrument&#x27;s range<");
  });

  it("reads the log's freshness and frames with its observations", async () => {
    const answers: Record<string, unknown> = {
      observations: {
        run_id: READINGS.runId,
        start: START,
        observations: READINGS.observations,
        freshness: READINGS.freshness,
        frames: READINGS.frames,
      },
      truth: { run_id: READINGS.runId, sensors: READINGS.truths },
    };
    const fetchFn = (async (url: string) =>
      new Response(
        JSON.stringify(answers[url.includes("/truth") ? "truth" : "observations"]),
      )) as typeof fetch;
    const state = await loadSensorReadings("climate_box", {}, fetchFn);

    expect(state).toEqual({ status: "loaded", readings: READINGS });
  });
});

describe("a selected camera's frames", () => {
  it("are counted, the latest one's metadata shown, and each one's moment", () => {
    const html = renderToStaticMarkup(
      <CameraFrames cameraId="camera" state={{ status: "loaded", readings: READINGS }} />,
    );

    expect(html).toContain('data-testid="camera-frames">2 frames by 1 min, each RGB and depth.<');
    expect(html).toContain('data-testid="camera-frame-from">x 0.60, y 3.20, z 2.20<');
    expect(html).toContain(
      'data-testid="camera-frame-picture">640 × 480 px, fx 457.01 px, fy 457.01 px<',
    );
    expect(html).toContain("<li>1 min</li><li>0 min</li>");
  });

  it("are none before the camera has taken one", () => {
    const html = renderToStaticMarkup(
      <CameraFrames cameraId="other" state={{ status: "loaded", readings: READINGS }} />,
    );

    expect(html).toContain("No frames yet.");
  });
});
