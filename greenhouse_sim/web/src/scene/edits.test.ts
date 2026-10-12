import { describe, expect, it } from "vitest";

import type { EnvironmentField } from "../fields/field";
import {
  type ScenarioSource,
  withCfdBoundaries,
  withClouds,
  withCompared,
  withField,
  withFieldView,
  withLevels,
  withoutCommand,
  withoutDaily,
  withProbes,
  withRepeated,
  withTime,
  withWeather,
} from "./edits";
import { sourceFromSearch } from "./source";

function scenario(search: string): ScenarioSource {
  const source = sourceFromSearch(search);
  if (source.kind !== "scenario") {
    throw new Error(`${search} is not a scenario's address`);
  }
  return source;
}

const PROBE = { x: 3, y: 3.2, z: 0.75 };

/** A still, even field two metres high, in cells of half a metre. */
const FIELD: EnvironmentField = {
  fieldId: "test",
  source: "test",
  timeS: 0,
  grid: {
    origin: { x: 0, y: 0, z: 0 },
    cell_size: { x: 0.5, y: 0.5, z: 0.5 },
    cells: { x: 2, y: 2, z: 4 },
  },
  channels: {
    velocity: {
      quantity: "velocity",
      unit: "m/s",
      components: 3,
      values: new Float32Array(16 * 3),
      minimum: 0,
      maximum: 0,
    },
    temperature: {
      quantity: "temperature",
      unit: "°C",
      components: 1,
      values: new Float32Array(16).fill(20),
      minimum: 20,
      maximum: 20,
    },
  },
};

describe("changing a scenario's source from its panels", () => {
  it("draws another field, keeping its probes and what it is compared with", () => {
    const drawn = scenario("?scenario=airflow_box&field=uniform&fieldView=slice&compare=vortex");
    const probed = withProbes(drawn, [PROBE]);

    expect(withField(probed, "buoyancy")).toEqual({
      kind: "scenario",
      scenarioId: "airflow_box",
      field: "buoyancy",
      compare: "vortex",
      probes: [PROBE],
    });
    // Compared with itself, it is compared with nothing.
    expect(withField(probed, "vortex").compare).toBeUndefined();
    expect(withField(probed, null)).toEqual({ kind: "scenario", scenarioId: "airflow_box" });
  });

  it("leaves out what is no longer asked for, rather than writing it empty", () => {
    const source = scenario("?scenario=climate_box&field=climate&schedule=60:fan:1&cfd=boundaries");

    expect(withProbes(withProbes(source, [PROBE]), [])).toEqual(source);
    expect(withCompared(withCompared(source, "uniform"), null)).toEqual(source);
    expect(withoutCommand(source, 0).schedule).toBeUndefined();
    expect(withCfdBoundaries(source, false).cfdBoundaries).toBeUndefined();
    expect(withWeather(withWeather(source, "cold_spring_day"), undefined)).toEqual(source);
    expect(withClouds(withClouds(source, 80), undefined)).toEqual(source);
    expect(withTime(withTime(source, 600), 0)).toEqual(source);
  });

  it("repeats a command every day at its time of day, and takes a daily one out", () => {
    const source = scenario(
      "?scenario=climate_box&field=climate&schedule=60:fan:1,151200:heater:1&daily=25200:heater:0",
    );
    const repeated = withRepeated(source, 1);

    expect(repeated.schedule).toEqual([{ timeS: 60, actuatorId: "fan", level: 1 }]);
    expect(repeated.daily).toEqual([
      { timeS: 25200, actuatorId: "heater", level: 0 },
      { timeS: 64800, actuatorId: "heater", level: 1 },
    ]);
    expect(withoutDaily(withoutDaily(repeated, 0), 0).daily).toBeUndefined();
    expect(withRepeated(source, 5)).toBe(source);
  });

  it("slices the field where it was sliced, or across its middle", () => {
    const sliced = scenario(
      "?scenario=climate_box&field=climate&fieldView=slice&slice=temperature:z:1.5",
    );
    const { slice: _, ...unsliced } = sliced;

    expect(withFieldView(sliced, "slice", FIELD).slice).toEqual({
      quantity: "temperature",
      axis: "z",
      position: 1.5,
    });
    expect(withFieldView(unsliced, "slice", FIELD).slice).toEqual({
      quantity: "temperature",
      axis: "z",
      position: 1,
    });
    expect(withFieldView(sliced, "arrows", FIELD)).not.toHaveProperty("slice");
  });

  it("overrides equipment at the moment drawn, or sets it from the start", () => {
    const start = scenario("?scenario=climate_box&field=climate&set=heater:1");
    expect(withLevels(start, { heater: 1, fan: 1 })).toMatchObject({
      levels: { heater: 1, fan: 1 },
    });

    const later = withTime(start, 600);
    const overridden = withLevels(later, { heater: 1, fan: 1 });

    // Only what changed is commanded, at the moment drawn.
    expect(overridden.levels).toEqual({ heater: 1 });
    expect(overridden.schedule).toEqual([{ timeS: 600, actuatorId: "fan", level: 1 }]);
  });
});
