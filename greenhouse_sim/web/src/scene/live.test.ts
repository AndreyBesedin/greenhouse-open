import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { formatInstant } from "../readouts";
import type { SceneSnapshot } from "./generated/snapshotTypes";
import { commandUrl, type LiveFrame, liveUrl, parseLiveFrame, sendLiveCommand } from "./live";
import { SUPPORTED_SCHEMA_VERSION } from "./schemaVersion";
import { searchFor, sourceFromSearch } from "./source";

const EXAMPLE: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../../public/scenes/example.json", import.meta.url), "utf8"),
);
const FRAME: LiveFrame = {
  sequence: 12,
  day: 9,
  timestamp: "2026-01-10T12:00:00Z",
  playing: true,
  speed: 1,
  snapshot: EXAMPLE,
};

function answering(status: number, body: unknown): typeof fetch {
  return async () => new Response(JSON.stringify(body), { status });
}

describe("following a scenario live", () => {
  it("is chosen with ?live= and streams from the scenario's live endpoint", () => {
    expect(sourceFromSearch("?live=climate_box")).toEqual({
      kind: "live",
      scenarioId: "climate_box",
    });
    expect(searchFor({ kind: "live", scenarioId: "climate_box" })).toBe("?live=climate_box");
    expect(liveUrl("climate_box")).toBe("/api/scenarios/climate_box/live");
  });

  it("accepts a frame whose scene passes the check", () => {
    expect(parseLiveFrame(JSON.stringify(FRAME))).toEqual({ ok: true, frame: FRAME });
  });

  it.each([
    ["not JSON", "{"],
    ["without a day", JSON.stringify({ ...FRAME, day: undefined })],
    ["with a fractional sequence", JSON.stringify({ ...FRAME, sequence: 1.5 })],
    ["without saying whether it plays", JSON.stringify({ ...FRAME, playing: undefined })],
    ["with a speed that is not a number", JSON.stringify({ ...FRAME, speed: "fast" })],
  ])("refuses a frame %s", (_, data) => {
    expect(parseLiveFrame(data).ok).toBe(false);
  });

  it("refuses a frame whose scene fails the check, saying why", () => {
    const broken = {
      ...FRAME,
      snapshot: { ...EXAMPLE, schema_version: SUPPORTED_SCHEMA_VERSION + 1 },
    };

    expect(parseLiveFrame(JSON.stringify(broken))).toEqual({
      ok: false,
      problems: [
        `schema version ${SUPPORTED_SCHEMA_VERSION + 1} is not the ${SUPPORTED_SCHEMA_VERSION} this viewer draws`,
      ],
    });
  });

  it("writes the simulated instant in UTC to the minute", () => {
    expect(formatInstant("2026-01-10T12:00:00Z")).toBe("2026-01-10 12:00 UTC");
  });
});

describe("controlling a live run", () => {
  it("sends each command to the run's own endpoint", () => {
    expect(commandUrl("climate_box", "pause")).toBe("/api/scenarios/climate_box/live/pause");
    expect(commandUrl("climate_box", "step")).toBe("/api/scenarios/climate_box/live/step");
    expect(commandUrl("climate_box", { speed: 0.25 })).toBe(
      "/api/scenarios/climate_box/live/speed?multiplier=0.25",
    );
  });

  it("reports a command the simulator took, refused or never received", async () => {
    const unreachable: typeof fetch = async () => {
      throw new TypeError("Failed to fetch");
    };

    expect(await sendLiveCommand("climate_box", "reset", answering(200, {}))).toEqual({ ok: true });
    expect(
      await sendLiveCommand(
        "climate_box",
        { speed: 3 },
        answering(400, { error: "no such speed" }),
      ),
    ).toEqual({ ok: false, problem: "the simulator answered 400: no such speed" });
    expect(await sendLiveCommand("climate_box", "play", answering(502, "Bad Gateway"))).toEqual({
      ok: false,
      problem: "the simulator answered 502",
    });
    expect(await sendLiveCommand("climate_box", "play", unreachable)).toEqual({
      ok: false,
      problem: "the simulator could not be reached",
    });
  });
});
