import { describe, expect, it } from "vitest";

import { portOffset, shellWord, simulatorServer } from "../simulatorApi.ts";

describe("the browser tests' simulator", () => {
  it("is served from a Python whose path holds a space, as a clone's may", () => {
    expect(simulatorServer(8766, "/home/a b/greenhouse-open/.venv/bin/python")).toBe(
      "'/home/a b/greenhouse-open/.venv/bin/python' -m greenhouse_sim.api --port 8766",
    );
  });

  it("quotes a quote too", () => {
    expect(shellWord("it's")).toBe(`'it'"'"'s'`);
  });
});

describe("the browser tests' ports", () => {
  it("are their own unless TEST_PORT_OFFSET moves them", () => {
    expect(portOffset(undefined)).toBe(0);
    expect(portOffset("")).toBe(0);
    expect(portOffset("20")).toBe(20);
  });

  it("are moved by whole numbers only", () => {
    for (const value of ["-1", "1.5", "ten"]) {
      expect(() => portOffset(value)).toThrow(`TEST_PORT_OFFSET=${value}`);
    }
  });
});
