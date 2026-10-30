import { describe, expect, it } from "vitest";

import { describeRunState, loadRunState, parseRunState, runStateUrl } from "./state";

// Ten minutes into the climate box's heated run, as the simulator serves
// what its processes hold.
const SERVED = {
  run_id: "climate_box-climate-4c7732e2",
  start: "2025-12-31T23:00:00Z",
  at: "2025-12-31T23:10:00Z",
  time_s: 600,
  day: 0,
  house_air: { temperature_c: 19.445, humidity_pct: 67.364, co2_ppm: 420 },
  crop_model: "simple",
  plants: 32,
  days_lived: 0,
  levels: { fan: 0, heater: 1 },
  commands_given: 1,
  latest_commands: [{ time_s: 0, actuator_id: "heater", level: 1 }],
  sensors: [
    {
      sensor_id: "temperature_front",
      state: "fresh",
      due_at: "2025-12-31T23:10:00Z",
      latest_at: "2025-12-31T23:10:00Z",
    },
    { sensor_id: "co2", state: "waiting", due_at: null, latest_at: null },
  ],
  cameras: [{ sensor_id: "front_camera", frames: 0, latest: null }],
};

function answering(body: unknown, status = 200): typeof fetch {
  return (async () => new Response(JSON.stringify(body), { status })) as typeof fetch;
}

describe("what each process of a run holds", () => {
  it("is asked for as the climate is", () => {
    expect(runStateUrl("climate_box", { levels: { heater: 1 }, time: 600 })).toBe(
      "/api/scenarios/climate_box/climate/state?set=heater:1&t=600",
    );
  });

  it("is read as served, and checked", async () => {
    const state = parseRunState(SERVED);
    expect(state).toMatchObject({
      runId: "climate_box-climate-4c7732e2",
      timeS: 600,
      houseAir: { temperatureC: 19.445, humidityPct: 67.364, co2Ppm: 420 },
      latestCommands: [{ timeS: 0, actuatorId: "heater", level: 1 }],
      cameras: [{ sensorId: "front_camera", frames: 0, latest: null }],
    });
    expect(parseRunState({ ...SERVED, house_air: null }).houseAir).toBeNull();
    expect(() => parseRunState({ ...SERVED, latest_commands: [{ time_s: 0 }] })).toThrow(
      "the run's state is not what the viewer expects",
    );
    expect(() =>
      parseRunState({ ...SERVED, cameras: [{ sensor_id: "c", frames: 1, latest: {} }] }),
    ).toThrow();
    expect(await loadRunState("/s", answering(SERVED))).toMatchObject({ status: "loaded" });
    expect(await loadRunState("/s", answering({}, 400))).toEqual({
      status: "unavailable",
      reason: "the simulator API answered 400",
    });
  });

  it("is said in words, a line for each process", () => {
    const said = describeRunState(parseRunState(SERVED));

    expect(said.clock).toBe("10 min (2025-12-31 23:10 UTC), run climate_box-climate-4c7732e2");
    expect(said.houseAir).toBe("19.45 °C, 67.36%, 420 ppm");
    expect(said.crop).toBe("32 plants, the simple daily model; no day lived yet");
    // A crop grown by area: no plants, the model by name, its last day.
    const byArea = {
      ...parseRunState(SERVED),
      plants: 0,
      cropModel: "reduced_tomgro",
      daysLived: 3,
    };
    expect(describeRunState(byArea).crop).toBe(
      "Reduced-State TOMGRO, by area on each row; last day 2",
    );
    expect(said.levels).toBe("fan 0%, heater 100%");
    expect(said.commands).toEqual(["0 min: heater 100%"]);
    expect(said.sensors).toEqual([
      { id: "temperature_front", stale: false, text: "temperature_front: fresh, latest 10 min" },
      { id: "co2", stale: false, text: "co2: waiting" },
    ]);
    expect(said.cameras).toEqual([{ id: "front_camera", text: "front_camera: 0 frames" }]);
    const bare = describeRunState(parseRunState({ ...SERVED, house_air: null, levels: {} }));
    expect(bare.houseAir).toBe("none: without equipment the run has no climate");
    expect(bare.levels).toBe("none");
  });
});
