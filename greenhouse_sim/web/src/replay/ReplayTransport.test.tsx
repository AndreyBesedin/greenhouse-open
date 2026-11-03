// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import { DAY_S } from "../clock";
import { button, choose, click, type Rendered, render, said, select } from "../testing/render";
import type { PositionState } from "./position";
import { canFollow, ReplayTransport, spanOf } from "./ReplayTransport";

function position(more: Partial<PositionState> = {}): PositionState {
  return {
    position_id: "p1",
    scenario_id: "reference_greenhouse",
    run_id: "run-1",
    epoch: 0,
    layout: "default",
    seed: 2,
    status: "running",
    started_at: "2026-03-01T00:00:00Z",
    simulated_now: "2026-03-18T06:00:00Z",
    time_s: 17 * DAY_S + 6 * 3600,
    day: 17,
    playing: false,
    following: false,
    seconds_per_day: 10,
    frontier_s: 41 * DAY_S,
    duration_s: 120 * DAY_S,
    start_s: 0,
    fork: null,
    targets: [],
    commands: [],
    crop: [],
    ...more,
  };
}

describe("what moves a position over a stored run", () => {
  let rendered: Rendered | undefined;
  afterEach(() => rendered?.unmount());

  function shown(state: PositionState) {
    const calls = {
      onPlay: vi.fn(),
      onPause: vi.fn(),
      onFollow: vi.fn(),
      onSeek: vi.fn(),
      onPace: vi.fn(),
    };
    rendered = render(<ReplayTransport position={state} {...calls} />);
    return { container: rendered.container, ...calls };
  }

  it("says where the position stands and how far the run is computed", () => {
    const { container } = shown(position());

    expect(said(container, "replay-moment")).toBe("Day 18, 06:00");
    expect(said(container, "replay-computed")).toBe("Computed to day 41 of 120");
  });

  it("plays, or pauses what plays", () => {
    const paused = shown(position());
    click(button(paused.container, "Play"));
    expect(paused.onPlay).toHaveBeenCalledOnce();
    rendered?.unmount();

    const playing = shown(position({ playing: true }));
    click(button(playing.container, "Pause"));
    expect(playing.onPause).toHaveBeenCalledOnce();
  });

  it("says why a move did nothing, and nothing when none was refused", () => {
    expect(shown(position()).container.querySelector('[role="alert"]')).toBeNull();
    rendered?.unmount();

    rendered = render(
      <ReplayTransport
        position={position()}
        refused="no position 'p1'"
        onPlay={vi.fn()}
        onPause={vi.fn()}
        onFollow={vi.fn()}
        onSeek={vi.fn()}
        onPace={vi.fn()}
      />,
    );
    expect(rendered.container.querySelector('[role="alert"]')?.textContent).toContain(
      "no position 'p1'",
    );
  });

  it("has nothing to play at the run's end, and plays from anywhere before it", () => {
    const atEnd = shown(position({ time_s: 120 * DAY_S, frontier_s: 120 * DAY_S }));
    expect(button(atEnd.container, "Play").disabled).toBe(true);
    rendered?.unmount();

    const atFrontier = shown(position({ time_s: 41 * DAY_S }));
    expect(button(atFrontier.container, "Play").disabled).toBe(false);
  });

  it("moves a day back or on, at the same time of day", () => {
    const { container, onSeek } = shown(position());

    click(button(container, "Next day"));
    click(button(container, "Previous day"));

    expect(onSeek.mock.calls).toEqual([[18 * DAY_S + 6 * 3600], [16 * DAY_S + 6 * 3600]]);
  });

  it("never moves past what is computed", () => {
    const { container, onSeek } = shown(position({ time_s: 41 * DAY_S }));

    click(button(container, "Next day"));

    expect(onSeek).toHaveBeenCalledWith(41 * DAY_S);
  });

  it("sets how fast a day plays, among the paces, and keeps one it has", () => {
    const { container, onPace } = shown(position({ seconds_per_day: 7 }));
    const pace = select(container, "Pace");

    expect([...pace.options].map((o) => o.textContent)).toContain("7 s a day");
    choose(pace, "30");
    expect(onPace).toHaveBeenCalledWith(30);
  });

  it("follows the newest day only while the run is being computed", () => {
    const running = shown(position());
    const follow = button(running.container, "Follow the newest day");
    expect(follow.getAttribute("aria-pressed")).toBe("false");
    click(follow);
    expect(running.onFollow).toHaveBeenCalledOnce();
    rendered?.unmount();

    for (const status of ["finished", "interrupted", "failed"] as const) {
      const done = shown(position({ status }));
      expect(done.container.textContent).not.toContain("Follow the newest day");
      rendered?.unmount();
    }
  });

  it("shows that it follows", () => {
    const { container } = shown(position({ following: true }));

    expect(button(container, "Follow the newest day").getAttribute("aria-pressed")).toBe("true");
  });

  it("stops following when its pressed button is pressed again, by pausing the position", () => {
    // A following position shows Play, so that nothing else can pause it.
    const { container, onPause, onFollow } = shown(position({ following: true, playing: false }));

    click(button(container, "Follow the newest day"));

    expect(onPause).toHaveBeenCalledOnce();
    expect(onFollow).not.toHaveBeenCalled();
  });

  it("is over the whole of the run, from its start to the frontier", () => {
    expect(spanOf(position())).toEqual({ startS: 0, frontierS: 41 * DAY_S, endS: 120 * DAY_S });
    // A fork holds nothing before the state it inherits.
    expect(spanOf(position({ start_s: 5 * DAY_S })).startS).toBe(5 * DAY_S);
    expect(canFollow(position({ status: "queued" }))).toBe(true);
    expect(canFollow(position({ status: "finished" }))).toBe(false);
  });
});
