// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DAY_S } from "../clock";
import { type Rendered, render } from "../testing/render";
import { ReplayTimeline } from "./ReplayTimeline";
import type { Span } from "./timeline";

const SPAN: Span = { startS: 0, frontierS: 41 * DAY_S, endS: 120 * DAY_S };
const WIDTH = 1200;

describe("the timeline over a stored run", () => {
  let rendered: Rendered | undefined;
  afterEach(() => rendered?.unmount());

  function shown(timeS: number, span: Span = SPAN) {
    const onSeek = vi.fn();
    rendered = render(<ReplayTimeline span={span} timeS={timeS} onSeek={onSeek} />);
    const handle = rendered.container.querySelector<HTMLElement>('[role="slider"]');
    const track = rendered.container.querySelector<HTMLElement>('[data-testid="replay-track"]');
    if (handle === null || track === null) {
      throw new Error("no timeline");
    }
    // A DOM has no layout: the track is as wide as a desktop's.
    track.getBoundingClientRect = () => ({ left: 100, width: WIDTH }) as DOMRect;
    return { handle, track, onSeek };
  }

  function pressed(target: HTMLElement, key: string): void {
    act(() => {
      target.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true }));
    });
  }

  function pointed(target: HTMLElement, type: string, clientX: number): void {
    act(() => {
      target.dispatchEvent(new MouseEvent(type, { clientX, bubbles: true }));
    });
  }

  it("is a slider over what is computed, that says its day and time", () => {
    const { handle } = shown(17 * DAY_S + 6 * 3600);

    expect(handle.getAttribute("aria-valuemin")).toBe("0");
    expect(handle.getAttribute("aria-valuemax")).toBe(String(41 * DAY_S));
    expect(handle.getAttribute("aria-valuetext")).toBe("Day 18, 06:00");
    expect(handle.getAttribute("aria-label")).toBe("Position in the run");
    expect(handle.tabIndex).toBe(0);
  });

  it("labels the days, and says what the fill and the hatching are", () => {
    shown(0);
    const text = rendered?.container.textContent ?? "";

    for (const label of ["day 0", "30", "60", "90", "120"]) {
      expect(text).toContain(label);
    }
    expect(text).toContain("computed, can be played");
    expect(text).toContain("not computed yet");
  });

  it("fills as far as the run is computed, and marks the frontier there", () => {
    shown(0);
    const filled = rendered?.container.querySelector<HTMLElement>(".replay-computed");

    expect(filled?.style.width).toBe(`${(41 / 120) * 100}%`);
  });

  it("is operated by the keys: an hour, a day, the ends", () => {
    const { handle, onSeek } = shown(10 * DAY_S);

    pressed(handle, "ArrowRight");
    pressed(handle, "PageUp");
    pressed(handle, "Home");
    pressed(handle, "End");
    pressed(handle, "x");

    expect(onSeek.mock.calls).toEqual([[10 * DAY_S + 3600], [11 * DAY_S], [0], [41 * DAY_S]]);
  });

  it("seeks to where the pointer is, as a whole minute", () => {
    const { track, onSeek } = shown(0);

    pointed(track, "pointerdown", 100 + WIDTH / 4);

    expect(onSeek).toHaveBeenCalledWith(30 * DAY_S);
  });

  it("never seeks past what is computed", () => {
    const { track, onSeek } = shown(0);

    pointed(track, "pointerdown", 100 + WIDTH * 0.9);

    expect(onSeek).toHaveBeenCalledWith(41 * DAY_S);
  });

  it("follows the pointer while it is down, and stops when it is up", () => {
    const { track, onSeek } = shown(0);

    pointed(track, "pointerdown", 100);
    pointed(track, "pointermove", 100 + WIDTH / 8);
    pointed(track, "pointerup", 100 + WIDTH / 8);
    pointed(track, "pointermove", 100 + WIDTH / 2);

    expect(onSeek).toHaveBeenCalledTimes(2);
  });
});
