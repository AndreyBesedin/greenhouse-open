import { readFileSync } from "node:fs";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Hud } from "../Hud";
import { formatInstant, formatSpeed } from "../readouts";
import { TimeControls } from "../TimeControls";
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
const PAUSED: LiveFrame = { ...FRAME, playing: false, speed: 4 };
const ignore = () => undefined;

function answering(status: number, body: unknown): typeof fetch {
  return async () => new Response(JSON.stringify(body), { status });
}

function controls(frame: LiveFrame | null, connected = true): string {
  return renderToStaticMarkup(
    <TimeControls frame={frame} connected={connected} onCommand={ignore} />,
  );
}

describe("following a scenario live", () => {
  it("is chosen with ?live= and streams from the scenario's live endpoint", () => {
    expect(sourceFromSearch("?live=gh_demo")).toEqual({ kind: "live", scenarioId: "gh_demo" });
    expect(searchFor({ kind: "live", scenarioId: "gh_demo" })).toBe("?live=gh_demo");
    expect(liveUrl("gh_demo")).toBe("/api/scenarios/gh_demo/live");
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

  it("shows the stream's state and the simulated day in the HUD", () => {
    const html = renderToStaticMarkup(
      <Hud
        sample={null}
        pointer={null}
        live={{ connection: "live", frame: FRAME, problem: null }}
        onPreset={ignore}
        onCommand={ignore}
      />,
    );
    const lost = renderToStaticMarkup(
      <Hud
        sample={null}
        pointer={null}
        live={{ connection: "disconnected", frame: FRAME, problem: null }}
        onPreset={ignore}
        onCommand={ignore}
      />,
    );

    expect(html).toContain('data-testid="stream-status">live<');
    expect(html).toContain("day 9 · 2026-01-10 12:00 UTC");
    expect(lost).toContain("disconnected, reconnecting…");
  });

  it("leaves the live rows out when nothing is followed", () => {
    const html = renderToStaticMarkup(
      <Hud sample={null} pointer={null} onPreset={ignore} onCommand={ignore} />,
    );

    expect(html).not.toContain("stream-status");
    expect(html).not.toContain("Time controls");
  });
});

describe("controlling a live run", () => {
  it("sends each command to the run's own endpoint", () => {
    expect(commandUrl("gh_demo", "pause")).toBe("/api/scenarios/gh_demo/live/pause");
    expect(commandUrl("gh_demo", "step")).toBe("/api/scenarios/gh_demo/live/step");
    expect(commandUrl("gh_demo", { speed: 0.25 })).toBe(
      "/api/scenarios/gh_demo/live/speed?multiplier=0.25",
    );
  });

  it("reports a command the simulator took, refused or never received", async () => {
    const unreachable: typeof fetch = async () => {
      throw new TypeError("Failed to fetch");
    };

    expect(await sendLiveCommand("gh_demo", "reset", answering(200, {}))).toEqual({ ok: true });
    expect(
      await sendLiveCommand("gh_demo", { speed: 3 }, answering(400, { error: "no such speed" })),
    ).toEqual({ ok: false, problem: "the simulator answered 400: no such speed" });
    expect(await sendLiveCommand("gh_demo", "play", answering(502, "Bad Gateway"))).toEqual({
      ok: false,
      problem: "the simulator answered 502",
    });
    expect(await sendLiveCommand("gh_demo", "play", unreachable)).toEqual({
      ok: false,
      problem: "the simulator could not be reached",
    });
  });

  it("offers pause while playing, and steps only while paused", () => {
    const playing = controls(FRAME);
    const paused = controls(PAUSED);

    expect(playing).toContain(">Pause</button>");
    expect(playing).toContain('<button type="button" disabled="">Step</button>');
    expect(paused).toContain(">Play</button>");
    expect(paused).toContain('<button type="button">Step</button>');
  });

  it("shows the speed the run plays at", () => {
    expect(controls(PAUSED)).toContain(`<option value="4" selected="">${formatSpeed(4)}</option>`);
    expect(formatSpeed(0.25)).toBe("0.25×");
  });

  it("is disabled until a frame arrives, and while the stream is lost", () => {
    const disabled = '<fieldset class="time-controls" aria-label="Time controls" disabled="">';

    expect(controls(null)).toContain(disabled);
    expect(controls(PAUSED, false)).toContain(disabled);
    expect(controls(PAUSED)).toContain(
      '<fieldset class="time-controls" aria-label="Time controls">',
    );
  });

  it("says why a command was not taken", () => {
    const html = renderToStaticMarkup(
      <Hud
        sample={null}
        pointer={null}
        live={{ connection: "live", frame: FRAME, problem: "the simulator answered 502" }}
        onPreset={ignore}
        onCommand={ignore}
      />,
    );

    expect(html).toContain('data-testid="command-problem">the simulator answered 502<');
  });
});
