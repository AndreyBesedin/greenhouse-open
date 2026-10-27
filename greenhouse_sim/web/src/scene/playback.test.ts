import { describe, expect, it, vi } from "vitest";

import {
  commandPlayback,
  followedMoment,
  loadPlayback,
  parsePlayback,
  playbackUrl,
} from "./playback";

const ANSWER = {
  scenario_id: "reference_greenhouse",
  run_id: "reference_greenhouse-climate-c562c827",
  layout: "default",
  epoch: 0,
  greenhouse_id: "reference_greenhouse",
  started_at: "2026-02-28T23:00:00Z",
  simulated_now: "2026-03-02T11:00:30Z",
  time_s: 129_630,
  day: 1,
  playing: true,
  seconds_per_day: 10,
  worked_out_s: 172_800,
  every_s: 300,
  targets: [[129_660, "heating_night", 22]],
  commands: [[129_630, "roof_vent", 0.5]],
};
const STATE = {
  runId: "reference_greenhouse-climate-c562c827",
  layout: "default",
  epoch: 0,
  startedAt: "2026-02-28T23:00:00Z",
  simulatedNow: "2026-03-02T11:00:30Z",
  timeS: 129_630,
  day: 1,
  playing: true,
  secondsPerDay: 10,
  workedOutS: 172_800,
  targets: [{ timeS: 129_660, target: "heating_night", valueC: 22 }],
  commands: [{ timeS: 129_630, actuatorId: "roof_vent", level: 0.5 }],
};

function answering(status: number, body: unknown): typeof fetch {
  return vi.fn(async () => new Response(JSON.stringify(body), { status }));
}

describe("a run played back, as the viewer reads it", () => {
  it("is read from the simulator's answer, and refused when it is not one", () => {
    expect(parsePlayback(ANSWER)).toEqual(STATE);
    expect(parsePlayback({ ...ANSWER, time_s: "late" })).toBeNull();
    expect(parsePlayback({ ...ANSWER, run_id: undefined })).toBeNull();
    // Which layout it plays is part of it (#271).
    expect(parsePlayback({ ...ANSWER, layout: undefined })).toBeNull();
    expect(parsePlayback(null)).toBeNull();
  });

  it("is drawn at its clock's minute", () => {
    expect(followedMoment(STATE)).toBe(129_600);
  });

  it("is loaded, or said not to be started, or not to be reachable", async () => {
    expect(await loadPlayback("reference_greenhouse", answering(200, ANSWER))).toEqual({
      status: "loaded",
      state: STATE,
    });
    expect(await loadPlayback("reference_greenhouse", answering(404, { error: "no" }))).toEqual({
      status: "unstarted",
    });
    expect(await loadPlayback("reference_greenhouse", answering(500, {}))).toEqual({
      status: "unavailable",
      reason: "the simulator answered 500",
    });
    const unreachable = vi.fn(async () => {
      throw new TypeError("fetch failed");
    });
    expect(await loadPlayback("reference_greenhouse", unreachable)).toEqual({
      status: "unavailable",
      reason: "the simulator could not be reached",
    });
  });

  it("is said not to be read when its answer is not JSON, rather than lost", async () => {
    const broken: typeof fetch = vi.fn(async () => new Response("{ truncated", { status: 200 }));

    expect(await loadPlayback("climate_box", broken)).toEqual({
      status: "unavailable",
      reason: "the playback's state is not what the viewer reads",
    });
    expect(await commandPlayback("climate_box", "play", broken)).toEqual({
      status: "unavailable",
      reason: "the playback's state is not what the viewer reads",
    });
  });

  it("is started and commanded by POST, answered with its new state", async () => {
    const fetchFn = answering(200, ANSWER);

    expect(await commandPlayback("reference_greenhouse", "start", fetchFn)).toEqual({
      status: "loaded",
      state: STATE,
    });
    await commandPlayback("reference_greenhouse", "pause", fetchFn);
    // Started over with a layout, its moves written as an address writes
    // them (#271).
    await commandPlayback("reference_greenhouse", "restart", fetchFn, "default~heater:-1:0.5");

    expect(vi.mocked(fetchFn).mock.calls.map(([url, init]) => [url, init?.method])).toEqual([
      [`${playbackUrl("reference_greenhouse")}/start`, "POST"],
      [`${playbackUrl("reference_greenhouse")}/pause`, "POST"],
      [`${playbackUrl("reference_greenhouse")}/restart?layout=default~heater:-1:0.5`, "POST"],
    ]);
  });
});
