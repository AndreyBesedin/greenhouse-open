import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { type SensorReadings, sensorsUrl } from "./readings";
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
  ],
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
  });

  it("shows its latest reading, and the truth beside it, for QA", () => {
    const html = renderToStaticMarkup(
      <SensorPanel sensorId="t" unit="°C" state={{ status: "loaded", readings: READINGS }} />,
    );

    expect(html).toContain('data-testid="sensor-reading">14.96 °C at 10 min<');
    expect(html).toContain('aria-label="Truth, for QA only"');
    expect(html).toContain('data-testid="sensor-truth">14.96 °C at 10 min<');
  });

  it("says when nothing gives its quantity", () => {
    const html = renderToStaticMarkup(
      <SensorPanel
        sensorId="par"
        unit="µmol/m²/s"
        state={{ status: "loaded", readings: READINGS }}
      />,
    );

    expect(html).toContain("No reading: nothing gives this quantity yet.");
    expect(html).toContain('data-testid="sensor-truth">none<');
  });
});
