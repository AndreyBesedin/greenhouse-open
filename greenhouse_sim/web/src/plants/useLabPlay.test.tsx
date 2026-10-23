// @vitest-environment jsdom
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { SceneSource } from "../scene/source";
import type { SetSource } from "../scene/useSource";
import { renderHook } from "../testing/renderHook";
import { FIRST_LAB_RUN, PLANT_LAB_LAST_DAY } from "./lab";
import { useLabPlay } from "./useLabPlay";

function lab(day: number): SceneSource {
  return { kind: "plants", ...FIRST_LAB_RUN, day };
}

type Props = { source: SceneSource; shownDay: number | null };

/** The lab's play over a source the test holds, as the viewer's address
 * holds it, and changes as the hook asks. */
function playing() {
  let source = lab(3);
  const setSource = vi.fn((change: SetSource) => {
    source = typeof change === "function" ? change(source) : change;
  });
  const hook = renderHook(
    ({ source: given, shownDay }: Props) => useLabPlay(given, shownDay, setSource),
    { source, shownDay: 3 },
  );
  return {
    hook,
    setSource,
    get source() {
      return source;
    },
  };
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useLabPlay", () => {
  it("moves the lab on a day once the day asked for is on show, as fast as its speed", () => {
    const play = playing();
    act(() => {
      play.hook.current.setSpeed(2);
      play.hook.current.setPlaying(true);
    });

    act(() => vi.advanceTimersByTime(499));
    expect(play.setSource).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(1));
    expect(play.source).toMatchObject({ kind: "plants", day: 4 });
  });

  it("waits while the day asked for is not on show yet", () => {
    const play = playing();
    play.hook.rerender({ source: lab(4), shownDay: 3 });
    act(() => play.hook.current.setPlaying(true));

    act(() => vi.advanceTimersByTime(5000));
    expect(play.setSource).not.toHaveBeenCalled();
  });

  it("stops on its last day", () => {
    const play = playing();
    play.hook.rerender({ source: lab(PLANT_LAB_LAST_DAY), shownDay: PLANT_LAB_LAST_DAY });
    act(() => play.hook.current.setPlaying(true));

    expect(play.hook.current.playing).toBe(false);
    act(() => vi.advanceTimersByTime(5000));
    expect(play.setSource).not.toHaveBeenCalled();
  });
});
