import { describe, expect, it } from "vitest";

import { describeSimulatorTime, simulatorTimeOf } from "./simulatorTime";

const ORIGIN = "http://localhost:5173";

function entry(name: string, timings: { name: string; duration: number }[] = []) {
  return {
    name,
    serverTiming: timings.map(({ name: metric, duration }) => ({
      name: metric,
      duration,
      description: "",
      toJSON: () => ({}),
    })),
  };
}

describe("the simulator's time for a request", () => {
  it("is what the API says in its Server-Timing header, by path", () => {
    expect(
      simulatorTimeOf(
        entry(`${ORIGIN}/api/scenarios/climate_box/fields/climate?t=600`, [
          { name: "sim", duration: 812.3 },
        ]),
        ORIGIN,
      ),
    ).toEqual({ path: "scenarios/climate_box/fields/climate", ms: 812.3 });
  });

  it("is none for another request, or one that does not say", () => {
    expect(simulatorTimeOf(entry(`${ORIGIN}/scenes/example.json`), ORIGIN)).toBeNull();
    expect(simulatorTimeOf(entry(`${ORIGIN}/api/health`), ORIGIN)).toBeNull();
    expect(
      simulatorTimeOf(
        entry("https://elsewhere.test/api/x", [{ name: "sim", duration: 1 }]),
        ORIGIN,
      ),
    ).toBeNull();
    expect(
      simulatorTimeOf(entry(`${ORIGIN}/api/health`, [{ name: "db", duration: 3 }]), ORIGIN),
    ).toBeNull();
  });

  it("is said in whole milliseconds", () => {
    expect(describeSimulatorTime({ path: "scenarios", ms: 0.4 })).toBe("0 ms for scenarios");
  });
});
