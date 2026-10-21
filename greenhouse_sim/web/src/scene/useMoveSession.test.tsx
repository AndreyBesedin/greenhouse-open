// @vitest-environment jsdom
import { act } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { type RenderedHook, renderHook } from "../testing/renderHook";
import type { PlaybackLoad } from "./playback";
import type { SceneSource } from "./source";
import { type MoveSessionControls, useMoveSession } from "./useMoveSession";
import type { SetSource } from "./useSource";

// The climate box's climate at noon of its third day.
const AT_NOON: SceneSource = {
  kind: "scenario",
  scenarioId: "climate_box",
  field: "climate",
  time: 2 * 86_400 + 43_200,
};
const BOTH_MOVED = "default~co2:0.3:0,heater:-1:0.5";

interface Props {
  source: SceneSource;
  sceneLoading: boolean;
}

/** The hook over a view whose source changes as the hook changes it, each
 * change kept, in order, beside what else happened. */
function session({
  followed = null,
  fetchFn = vi.fn() as unknown as typeof fetch,
  source = AT_NOON,
}: {
  followed?: string | null;
  fetchFn?: typeof fetch;
  source?: SceneSource;
} = {}) {
  const happened: string[] = [];
  const changes: SceneSource[] = [];
  const played: PlaybackLoad[] = [];
  let props: Props = { source, sceneLoading: false };
  let hook: RenderedHook<Props, MoveSessionControls> | null = null;
  const setSource = (change: SetSource) => {
    const next = typeof change === "function" ? change(props.source) : change;
    changes.push(next);
    happened.push("source");
    // The view asks for the scene of the source changed, as the viewer does.
    props = { ...props, source: next, sceneLoading: true };
    hook?.rerender(props);
  };
  hook = renderHook(
    ({ source: shown, sceneLoading }: Props) =>
      useMoveSession({
        source: shown,
        setSource,
        defaultLayout: "default",
        followed,
        onPlayback: (load) => {
          happened.push("playback");
          played.push(load);
        },
        sceneLoading,
        fetchFn,
      }),
    props,
  );
  const rendered = hook;
  return {
    hook: rendered,
    changes,
    played,
    happened,
    /** The view as it is next drawn: another source, or the scene arrived. */
    show(next: Partial<Props>) {
      props = { ...props, ...next };
      rendered.rerender(props);
    },
  };
}

function playbackAnswer(layout: string): Response {
  return new Response(
    JSON.stringify({
      run_id: "climate_box-climate-0f00ba11",
      layout,
      epoch: 0,
      simulated_now: "2026-03-01T00:00:00Z",
      time_s: 0,
      day: 0,
      playing: true,
      seconds_per_day: 10,
      worked_out_s: 0,
    }),
  );
}

describe("a Move session", () => {
  let current: { hook: RenderedHook<Props, MoveSessionControls> } | undefined;
  afterEach(() => current?.hook.unmount());

  it("holds its moves as a draft, and asks the simulator for nothing", () => {
    const fetchFn = vi.fn() as unknown as typeof fetch;
    const view = session({ fetchFn });
    current = view;
    act(() => view.hook.current.start());
    act(() => view.hook.current.move("heater", { dx: -0.96, dy: 0.53 }));
    act(() => view.hook.current.move("co2", { dx: 0.3, dy: 0 }));

    expect(view.hook.current.session).toMatchObject({ from: undefined, to: BOTH_MOVED });
    expect(view.hook.current.changed).toBe(true);
    expect(view.changes).toEqual([]);
    expect(fetchFn).not.toHaveBeenCalled();
  });

  it("applies them all at once, at the run's start, in one change of the view", async () => {
    const view = session();
    current = view;
    act(() => view.hook.current.start());
    act(() => view.hook.current.move("heater", { dx: -1, dy: 0.5 }));
    act(() => view.hook.current.move("co2", { dx: 0.3, dy: 0 }));

    await act(async () => view.hook.current.apply());

    // One change, so one page of the browser's history: Back takes it back.
    expect(view.changes).toEqual([
      { kind: "scenario", scenarioId: "climate_box", field: "climate", layout: BOTH_MOVED },
    ]);
    // Its scene on its way, the moves stay drawn; arrived, the session ends.
    expect(view.hook.current.session).toMatchObject({ applying: true, to: BOTH_MOVED });
    view.show({ sceneLoading: false });
    expect(view.hook.current.session).toBeNull();
  });

  it("is cancelled, the view as it was", () => {
    const view = session();
    current = view;
    act(() => view.hook.current.start());
    act(() => view.hook.current.move("heater", { dx: -1, dy: 0.5 }));

    act(() => view.hook.current.cancel());

    expect(view.hook.current.session).toBeNull();
    expect(view.changes).toEqual([]);
  });

  it("moves an item its layout already moves further, or puts it back, or everything", async () => {
    const view = session({ source: { ...AT_NOON, layout: "default~heater:-1:0.5" } });
    current = view;
    act(() => view.hook.current.start());
    expect(view.hook.current.changed).toBe(false);

    act(() => view.hook.current.move("heater", { dx: -0.5, dy: 0 }));
    expect(view.hook.current.session?.to).toBe("default~heater:-1.5:0.5");
    act(() => view.hook.current.putBack("heater"));
    expect(view.hook.current.session?.to).toBeUndefined();
    act(() => view.hook.current.move("co2", { dx: 0.3, dy: 0 }));
    act(() => view.hook.current.putEverythingBack());
    expect(view.hook.current.session?.to).toBeUndefined();
    expect(view.hook.current.changed).toBe(true);

    await act(async () => view.hook.current.apply());
    // The scenario's own layout, from the run's start.
    expect(view.changes).toEqual([
      { kind: "scenario", scenarioId: "climate_box", field: "climate" },
    ]);
  });

  it("ends once the view shows another layout, as Back does", () => {
    const view = session();
    current = view;
    act(() => view.hook.current.start());
    act(() => view.hook.current.move("heater", { dx: -1, dy: 0.5 }));

    act(() => view.show({ source: { ...AT_NOON, layout: "default~fan:1:0" } }));

    expect(view.hook.current.session).toBeNull();
  });

  it("following, starts the run played back over with its layout first, and the view follows it from its start", async () => {
    const fetchFn = vi.fn(async () => playbackAnswer("default~heater:-1.0:0.5"));
    const view = session({ followed: "climate_box", fetchFn: fetchFn as unknown as typeof fetch });
    current = view;
    act(() => view.hook.current.start());
    act(() => view.hook.current.move("heater", { dx: -1, dy: 0.5 }));

    await act(async () => view.hook.current.apply());

    expect(fetchFn.mock.calls.map((call) => [...call] as unknown[])).toEqual([
      [
        "/api/scenarios/climate_box/playback/restart?layout=default~heater:-1:0.5",
        { method: "POST" },
      ],
    ]);
    expect(view.happened).toEqual(["playback", "source"]);
    expect(view.played).toMatchObject([
      { status: "loaded", state: { layout: "default~heater:-1.0:0.5", timeS: 0 } },
    ]);
    expect(view.changes).toEqual([
      {
        kind: "scenario",
        scenarioId: "climate_box",
        field: "climate",
        layout: "default~heater:-1:0.5",
      },
    ]);
  });

  it("following, keeps its moves and says why, if the run played back cannot start over", async () => {
    const fetchFn = vi.fn(async () => new Response("{}", { status: 400 }));
    const view = session({ followed: "climate_box", fetchFn: fetchFn as unknown as typeof fetch });
    current = view;
    act(() => view.hook.current.start());
    act(() => view.hook.current.move("heater", { dx: -1, dy: 0.5 }));

    await act(async () => view.hook.current.apply());

    expect(view.changes).toEqual([]);
    expect(view.hook.current.session).toMatchObject({
      applying: false,
      to: "default~heater:-1:0.5",
      failure: "the simulator answered 400",
    });
  });
});
