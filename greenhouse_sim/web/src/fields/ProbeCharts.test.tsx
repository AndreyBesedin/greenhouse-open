import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
  type ClimateProbes,
  chartPoints,
  chartRange,
  isClimateProbes,
  loadProbeCharts,
  ProbeCharts,
  probeChartsUrl,
} from "./ProbeCharts";

const READINGS: ClimateProbes = {
  times_s: [0, 60, 120],
  probes: [
    {
      point: { x: 10.5, y: 1, z: 0.75 },
      controlled: {
        temperature_c: [16, 25, 30],
        humidity_pct: [85, 60, 40],
        speed_m_s: [0, 0, 0],
      },
      all_off: { temperature_c: [16, 14, 12], humidity_pct: [85, 90, 95], speed_m_s: [0, 0, 0] },
    },
  ],
};

describe("probes' charts through a climate run", () => {
  it("are asked for as the climate is, with the probes, up to the moment drawn", () => {
    expect(
      probeChartsUrl("climate_box", {
        probes: [{ x: 10.5, y: 1, z: 0.75 }],
        levels: { heater: 1 },
        openings: { roof_vent: 1 },
        schedule: [{ timeS: 300, actuatorId: "heater", level: 0 }],
        time: 600,
      }),
    ).toBe(
      "/api/scenarios/climate_box/climate/probes?probes=10.5:1:0.75&set=heater:1&open=roof_vent:1&schedule=300:heater:0&t=600",
    );
    expect(probeChartsUrl("climate_box", { probes: [{ x: 1, y: 2, z: 3 }] })).toBe(
      "/api/scenarios/climate_box/climate/probes?probes=1:2:3",
    );
    expect(
      probeChartsUrl("climate_box", { probes: [{ x: 1, y: 2, z: 3 }], weather: "cold_spring_day" }),
    ).toBe("/api/scenarios/climate_box/climate/probes?probes=1:2:3&weather=cold_spring_day");
  });

  it("span both runs' values, across the run's hour, the highest at the top", () => {
    const range = chartRange([16, 25, 30], [16, 14, 12]);

    expect(range).toEqual({ min: 12, max: 30 });
    expect(chartRange([0, 0], [0])).toEqual({ min: -1, max: 1 });
    expect(chartPoints([0, 1800, 3600], [12, 21, 30], range)).toBe("0.0,70.0 120.0,35.0 240.0,0.0");
  });

  it("draw a line for each run, and say what both read at the moment drawn", () => {
    const html = renderToStaticMarkup(
      <ProbeCharts state={{ status: "loaded", probes: READINGS }} time={120} />,
    );

    expect(html).toContain('aria-label="Probe charts"');
    expect(html.match(/<polyline/g)).toHaveLength(6);
    expect(html).toContain('aria-label="P1 temperature, 12.00 to 30.00 °C"');
    expect(html).toContain(
      'data-testid="chart-P1-temperature_c">temperature 30.00 °C, all off 12.00 °C<',
    );
    expect(html).toContain(
      'data-testid="chart-P1-humidity_pct">humidity 40.00 %, all off 95.00 %<',
    );
  });

  it("say when they are being read or cannot be", async () => {
    expect(renderToStaticMarkup(<ProbeCharts state={{ status: "loading" }} time={0} />)).toContain(
      "Reading the probes through the run",
    );
    expect(renderToStaticMarkup(<ProbeCharts state={{ status: "none" }} time={0} />)).toBe("");
    const refused = await loadProbeCharts("/x", async () => new Response("", { status: 404 }));
    expect(refused).toEqual({ status: "unavailable", reason: "the simulator API answered 404" });
    const odd = await loadProbeCharts("/x", async () => new Response("{}", { status: 200 }));
    expect(odd.status).toBe("unavailable");
    expect(isClimateProbes(READINGS)).toBe(true);
  });
});
