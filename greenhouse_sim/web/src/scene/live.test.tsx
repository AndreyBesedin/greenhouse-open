import { readFileSync } from "node:fs";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { Hud } from "../Hud";
import { formatInstant } from "../readouts";
import type { SceneSnapshot } from "./generated/snapshotTypes";
import { liveUrl, parseLiveFrame } from "./live";
import { searchFor, sourceFromSearch } from "./source";

const EXAMPLE: SceneSnapshot = JSON.parse(
  readFileSync(new URL("../../public/scenes/example.json", import.meta.url), "utf8"),
);
const FRAME = { sequence: 12, day: 9, timestamp: "2026-01-10T12:00:00Z", snapshot: EXAMPLE };
const ignore = () => undefined;

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
  ])("refuses a frame %s", (_, data) => {
    expect(parseLiveFrame(data).ok).toBe(false);
  });

  it("refuses a frame whose scene fails the check, saying why", () => {
    const broken = { ...FRAME, snapshot: { ...EXAMPLE, schema_version: 2 } };

    expect(parseLiveFrame(JSON.stringify(broken))).toEqual({
      ok: false,
      problems: ["schema version 2 is not the 1 this viewer draws"],
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
        live={{ connection: "live", frame: FRAME }}
        onPreset={ignore}
      />,
    );
    const lost = renderToStaticMarkup(
      <Hud
        sample={null}
        pointer={null}
        live={{ connection: "disconnected", frame: FRAME }}
        onPreset={ignore}
      />,
    );

    expect(html).toContain('data-testid="stream-status">live<');
    expect(html).toContain("day 9 · 2026-01-10 12:00 UTC");
    expect(lost).toContain("disconnected, reconnecting…");
  });

  it("leaves the live rows out when nothing is followed", () => {
    const html = renderToStaticMarkup(<Hud sample={null} pointer={null} onPreset={ignore} />);

    expect(html).not.toContain("stream-status");
  });
});
