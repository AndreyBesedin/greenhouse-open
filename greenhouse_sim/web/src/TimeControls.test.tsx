// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { afterEach, describe, expect, it, vi } from "vitest";

import { Hud } from "./Hud";
import { formatSpeed } from "./readouts";
import type { SceneSnapshot } from "./scene/generated/snapshotTypes";
import type { LiveFrame } from "./scene/live";
import { TimeControls } from "./TimeControls";
import { button, choose, click, type Rendered, render, said, select } from "./testing/render";

// Read by its path: the DOM environment's URL is not one Node's files take.
const EXAMPLE: SceneSnapshot = JSON.parse(
  readFileSync(
    resolve(dirname(fileURLToPath(import.meta.url)), "../public/scenes/example.json"),
    "utf8",
  ),
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

describe("controlling a live run", () => {
  let drawn: Rendered | undefined;
  afterEach(() => drawn?.unmount());

  function controls(frame: LiveFrame | null, connected = true, onCommand = ignore) {
    drawn = render(<TimeControls frame={frame} connected={connected} onCommand={onCommand} />);
    return drawn.container;
  }

  it("pauses a run that plays, and steps only one that is paused", () => {
    const onCommand = vi.fn();
    const playing = controls(FRAME, true, onCommand);

    click(button(playing, "Pause"));
    expect(button(playing, "Step").disabled).toBe(true);
    drawn?.rerender(<TimeControls frame={PAUSED} connected onCommand={onCommand} />);
    click(button(playing, "Play"));
    click(button(playing, "Step"));
    click(button(playing, "Reset"));

    expect(onCommand.mock.calls).toEqual([["pause"], ["play"], ["step"], ["reset"]]);
  });

  it("shows the speed the run plays at, and asks for another", () => {
    const onCommand = vi.fn();
    const speed = select(controls(PAUSED, true, onCommand), "Speed");
    expect(speed.selectedOptions[0]?.textContent).toBe(formatSpeed(4));

    choose(speed, "0.25");

    expect(onCommand).toHaveBeenCalledWith({ speed: 0.25 });
    expect(formatSpeed(0.25)).toBe("0.25×");
  });

  it("is disabled until a frame arrives, and while the stream is lost", () => {
    const usable = (container: HTMLElement) => !button(container, "Reset").matches(":disabled");

    expect(usable(controls(null))).toBe(false);
    drawn?.unmount();
    expect(usable(controls(PAUSED, false))).toBe(false);
    drawn?.unmount();
    expect(usable(controls(PAUSED))).toBe(true);
  });
});

describe("a live run in the HUD", () => {
  let hud: Rendered | undefined;
  afterEach(() => hud?.unmount());

  it("shows the stream's state and the simulated day", () => {
    hud = render(
      <Hud
        sample={null}
        pointer={null}
        live={{ connection: "live", frame: FRAME, problem: null }}
        onPreset={ignore}
        onCommand={ignore}
      />,
    );
    expect(said(hud.container, "stream-status")).toBe("live");
    expect(said(hud.container, "simulation-time")).toBe("day 9 · 2026-01-10 12:00 UTC");

    hud.rerender(
      <Hud
        sample={null}
        pointer={null}
        live={{ connection: "disconnected", frame: FRAME, problem: null }}
        onPreset={ignore}
        onCommand={ignore}
      />,
    );

    expect(said(hud.container, "stream-status")).toBe("disconnected, reconnecting…");
  });

  it("says why a command was not taken", () => {
    hud = render(
      <Hud
        sample={null}
        pointer={null}
        live={{ connection: "live", frame: FRAME, problem: "the simulator answered 502" }}
        onPreset={ignore}
        onCommand={ignore}
      />,
    );

    expect(said(hud.container, "command-problem")).toBe("the simulator answered 502");
  });

  it("leaves the live rows and the time controls out when nothing is followed", () => {
    hud = render(<Hud sample={null} pointer={null} onPreset={ignore} onCommand={ignore} />);

    expect(said(hud.container, "stream-status")).toBeNull();
    expect(hud.container.querySelector('[aria-label="Time controls"]')).toBeNull();
  });
});
