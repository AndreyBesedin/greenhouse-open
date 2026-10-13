import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { BranchComparison, describeBranches } from "./BranchComparison";
import { checkpointRun, comparable, comparisonKey, loadComparison } from "./branches";
import { parseCheckpoint } from "./checkpoints";

const CHECKPOINT = parseCheckpoint({
  checkpoint_id: "c1",
  scenario_id: "climate_box",
  layout: "default",
  weather: "default",
  levels: {},
  openings: {},
  commands: [[600, "heater", 1]],
  daily: null,
  day: 1,
  time_s: 86400,
  plants: 0,
});
const SERIES = (temperature: number[]) => ({
  temperature_c: temperature,
  humidity_pct: temperature.map(() => 80),
  co2_ppm: temperature.map(() => 420),
  removed_kg: temperature.map(() => 0),
  condensed_kg: temperature.map(() => 0),
});
const HOUSE = (temperature: number[]) => ({
  times_s: [93600, 93660],
  controlled: SERIES(temperature),
  all_off: SERIES(temperature),
});
const LOG = (values: number[]) => ({
  start: "2026-01-01T00:00:00+00:00",
  observations: values.map((value, index) => ({
    sensor_id: "temperature_front",
    observation_type: "AIR_TEMPERATURE_C",
    timestamp: new Date(Date.UTC(2026, 0, 2, 2, index)).toISOString(),
    value,
  })),
});

describe("a branch comparison", () => {
  const request = {
    scenarioId: "climate_box",
    a: checkpointRun(CHECKPOINT, 93660),
    b: { schedule: CHECKPOINT.commands, time: 93660 },
    fromDay: 1,
    sensorId: "temperature_front",
    plantId: null,
  };

  it("runs the checkpoint's run on unchanged, at the moment drawn", () => {
    expect(checkpointRun(CHECKPOINT, 93660)).toEqual({
      schedule: [{ timeS: 600, actuatorId: "heater", level: 1 }],
      time: 93660,
    });
    expect(checkpointRun({ ...CHECKPOINT, daily: [], weather: "default@80" }, 0)).toEqual({
      schedule: CHECKPOINT.commands,
      daily: [],
      weather: "default@80",
      time: 0,
    });
    expect(comparisonKey(request)).toContain("/climate/house?schedule=600:heater:1&t=93660");
  });

  it("pairs each branch's house air and readings at the same moments", async () => {
    const answers = [HOUSE([20, 21]), HOUSE([18, 17]), LOG([20.5, 21.5]), LOG([18.5])];
    const fetchFn = vi.fn(async () => Response.json(answers.shift())) as unknown as typeof fetch;

    const state = await loadComparison(request, fetchFn);

    expect(state).toEqual({
      status: "loaded",
      comparison: {
        house: { at: [93600, 93660], a: [20, 21], b: [18, 17] },
        sensor: {
          sensorId: "temperature_front",
          readings: { at: [93600], a: [20.5], b: [18.5] },
        },
        plant: null,
      },
    });
    const refused = (async () => new Response("{}", { status: 400 })) as typeof fetch;
    expect(await loadComparison(request, refused)).toEqual({
      status: "unavailable",
      reason: "the simulator API answered 400",
    });
  });

  it("finds a scene's first temperature sensor and first plant drawn by organ", () => {
    const entity = (kind: string, properties: Record<string, string>) =>
      ({ kind, properties }) as never;
    expect(
      comparable({
        entities: [
          entity("SENSOR", { sensor_id: "co2", sensor_kind: "co2" }),
          entity("SENSOR", { sensor_id: "temperature_front", sensor_kind: "temperature" }),
          entity("LEAF", { organ_id: "p1_n01_leaf", plant_id: "p1" }),
        ],
      } as never),
    ).toEqual({ sensorId: "temperature_front", plantId: "p1" });
    expect(comparable(null)).toEqual({ sensorId: null, plantId: null });
  });

  it("says each branch's latest, and nothing before the checkpoint", () => {
    expect(describeBranches({ at: [0, 1], a: [20, 21.04], b: [18, 16.96] }, "°C")).toBe(
      "A 21.0 °C, B 17.0 °C",
    );
    expect(describeBranches({ at: [], a: [], b: [] }, "°C")).toBe("nothing yet");
    const before = renderToStaticMarkup(
      <BranchComparison checkpoint={CHECKPOINT} request={request} time={3600} />,
    );
    expect(before).toContain("The moment drawn lies before the checkpoint.");
  });
});
