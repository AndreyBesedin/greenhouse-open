// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import { PlaybackPanel } from "./PlaybackPanel";
import type { PlaybackLoad } from "./scene/playback";
import { button, click, type Rendered, render, said } from "./testing/render";

const LOADED: PlaybackLoad = {
  status: "loaded",
  state: {
    runId: "reference_greenhouse-climate-c562c827",
    epoch: 1,
    simulatedNow: "2026-03-02T11:00:00Z",
    timeS: 129_600,
    day: 1,
    playing: true,
    secondsPerDay: 10,
    workedOutS: 4 * 86_400,
  },
};

describe("the run a view follows as it is played back", () => {
  let panel: Rendered | undefined;
  afterEach(() => panel?.unmount());

  function shown(load: PlaybackLoad, changed: string[] = []) {
    const calls = {
      onCommand: vi.fn(),
      onStart: vi.fn(),
      onOwnRun: vi.fn(),
      onStop: vi.fn(),
    };
    panel = render(<PlaybackPanel load={load} changed={changed} {...calls} />);
    return { container: panel.container, ...calls };
  }

  it("says which run, its epoch, where its clock stands and how fast it plays", () => {
    const { container, onCommand } = shown(LOADED);

    expect(said(container, "playback-status")).toBe(
      "Following run reference_greenhouse-climate-c562c827, epoch 1: day 1, 12 h 00 min, " +
        "playing a day in 10 s; worked out to day 4.",
    );
    click(button(container, "Pause"));
    click(button(container, "Start over"));
    expect(onCommand.mock.calls).toEqual([["pause"], ["restart"]]);
  });

  it("offers to play the run back when nobody has yet", () => {
    const { container, onStart } = shown({ status: "unstarted" });

    click(button(container, "Play it back"));
    expect(onStart).toHaveBeenCalledOnce();
  });

  it("says when the view draws another run than the one played back", () => {
    const { container, onOwnRun, onStop } = shown(LOADED, ["its weather", "its commands"]);

    expect(said(container, "playback-another-run")).toContain(
      "it changes its weather, its commands.",
    );
    click(button(container, "Draw the run played back"));
    click(button(container, "Stop following"));
    expect(onOwnRun).toHaveBeenCalledOnce();
    expect(onStop).toHaveBeenCalledOnce();
  });
});
