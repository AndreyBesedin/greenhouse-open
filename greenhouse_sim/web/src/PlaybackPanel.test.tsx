// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import { DAY_S } from "./clock";
import { PlaybackPanel } from "./PlaybackPanel";
import type { PlaybackLoad, PlaybackState } from "./scene/playback";
import { button, click, type Rendered, render, said } from "./testing/render";

const PLAYING: PlaybackState = {
  runId: "reference_greenhouse-climate-c562c827",
  layout: "default",
  epoch: 1,
  simulatedNow: "2026-03-02T11:00:00Z",
  timeS: 129_600,
  day: 1,
  playing: true,
  secondsPerDay: 10,
  workedOutS: 4 * 86_400,
};
const LOADED: PlaybackLoad = { status: "loaded", state: PLAYING };
// The run's length, as the scenario's list says it.
const DAYS = 14;

describe("the run a view follows as it is played back", () => {
  let panel: Rendered | undefined;
  afterEach(() => panel?.unmount());

  function shown(load: PlaybackLoad, changed: string[] = [], days: number | null = DAYS) {
    const calls = {
      onCommand: vi.fn(),
      onStart: vi.fn(),
      onOwnRun: vi.fn(),
      onStop: vi.fn(),
    };
    const drawn = (next: PlaybackLoad) => (
      <PlaybackPanel load={next} days={days} changed={changed} {...calls} />
    );
    const rendered = render(drawn(load));
    panel = rendered;
    return {
      container: rendered.container,
      /** Draws it again, as the playback next answers. */
      redraw: (next: PlaybackLoad) => rendered.rerender(drawn(next)),
      ...calls,
    };
  }

  /** The run's progress bar: where it stands, and where the run ends. */
  function progress(container: HTMLElement): { value: number; max: number } | null {
    const bar = container.querySelector('progress[aria-label="The run\'s progress"]');
    return bar === null
      ? null
      : { value: Number(bar.getAttribute("value")), max: Number(bar.getAttribute("max")) };
  }

  it("says which run, its epoch, how fast it plays and where its clock stands in the run", () => {
    const { container, onCommand } = shown(LOADED);

    expect(said(container, "playback-status")).toBe(
      "Following run reference_greenhouse-climate-c562c827, epoch 1: " +
        "playing a day in 10 s; worked out to day 4.",
    );
    // One progress across the run's days: a day and a half of fourteen.
    expect(progress(container)).toEqual({ value: 129_600, max: 14 * DAY_S });
    expect(said(container, "playback-progress")).toBe("day 1, 12 h 00 min of 14 days");
    click(button(container, "Pause"));
    click(button(container, "Start over"));
    expect(onCommand.mock.calls).toEqual([["pause"], ["restart"]]);
  });

  it("moves its progress on with the clock from one day into the next, never back", () => {
    // A time-of-day slider would go back at each midnight (#270): late on
    // day 1, early on day 2.
    const { container, redraw } = shown(LOADED);
    const reached: number[] = [];
    for (const timeS of [DAY_S + 20 * 3600, 2 * DAY_S + 5 * 3600, 2 * DAY_S + 14 * 3600]) {
      redraw({ status: "loaded", state: { ...PLAYING, timeS } });
      reached.push(progress(container)?.value ?? Number.NaN);
    }

    expect(reached).toEqual([DAY_S + 20 * 3600, 2 * DAY_S + 5 * 3600, 2 * DAY_S + 14 * 3600]);
    expect(said(container, "playback-progress")).toBe("day 2, 14 h 00 min of 14 days");
  });

  it("paused, offers to play, and its progress says the minute the view draws", () => {
    const { container, onCommand } = shown({
      status: "loaded",
      state: { ...PLAYING, playing: false, timeS: 2 * DAY_S + 3 * 3600 + 59.7 * 60 },
    });

    expect(said(container, "playback-status")).toContain("epoch 1: paused; worked out to day 4.");
    expect(said(container, "playback-progress")).toBe("day 2, 3 h 59 min of 14 days");
    click(button(container, "Play"));
    expect(onCommand).toHaveBeenCalledExactlyOnceWith("play");
  });

  it("says where the clock stands before it knows how long the run lasts, without a bar", () => {
    const { container } = shown(LOADED, [], null);

    expect(progress(container)).toBeNull();
    expect(said(container, "playback-progress")).toBe("day 1, 12 h 00 min");
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
