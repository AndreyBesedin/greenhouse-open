import { describe, expect, it } from "vitest";

import {
  equipmentUrl,
  governedLevels,
  loadEquipment,
  parseEquipment,
  runningThermostat,
} from "./equipment";

// The reference greenhouse's equipment an hour into its run, as the
// simulator answers it: its thermostat runs its heater, full on.
const ANSWER = {
  time_s: 3600,
  levels: { fan_left: 0, fan_right: 0, heater: 1, dehumidifier: 0 },
  thermostat: { actuator_id: "heater", setpoint_c: 16, day_c: 18, night_c: 16, runs: true },
};

function answering(body: unknown, status = 200): typeof fetch {
  return async () => new Response(JSON.stringify(body), { status });
}

describe("a run's equipment at a moment", () => {
  it("is asked for as the climate is, at the moment drawn", () => {
    expect(
      equipmentUrl("reference_greenhouse", {
        time: 3600,
        schedule: [{ timeS: 600, actuatorId: "heater", level: 0 }],
      }),
    ).toBe("/api/scenarios/reference_greenhouse/climate/equipment?schedule=600:heater:0&t=3600");
  });

  it("is read as the simulator says it, checked rather than trusted", () => {
    expect(parseEquipment(ANSWER)).toEqual({
      timeS: 3600,
      levels: ANSWER.levels,
      thermostat: { actuatorId: "heater", setpointC: 16, runs: true },
    });
    expect(parseEquipment({ ...ANSWER, thermostat: null }).thermostat).toBeNull();
    expect(() => parseEquipment({ ...ANSWER, levels: { heater: "on" } })).toThrow(
      "not what the viewer expects",
    );
    expect(() => parseEquipment({ ...ANSWER, thermostat: { actuator_id: "heater" } })).toThrow();
  });

  it("gives the scene its thermostat's heater while the thermostat runs it, and nothing else", async () => {
    const loaded = await loadEquipment("/x", answering(ANSWER));

    expect(runningThermostat(loaded)?.setpointC).toBe(16);
    expect(governedLevels(loaded)).toEqual({ heater: 1 });
    // Taken over by a command, the heater is where the commands put it.
    const commanded = await loadEquipment(
      "/x",
      answering({ ...ANSWER, thermostat: { ...ANSWER.thermostat, runs: false } }),
    );
    expect(runningThermostat(commanded)).toBeNull();
    expect(governedLevels(commanded)).toEqual({});
    expect(governedLevels({ status: "loading" })).toEqual({});
  });

  it("says why it could not be read", async () => {
    expect(await loadEquipment("/x", answering({}, 500))).toEqual({
      status: "unavailable",
      reason: "the simulator API answered 500",
    });
  });
});
