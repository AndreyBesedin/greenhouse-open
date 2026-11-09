// @vitest-environment jsdom
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { type RenderedHook, renderHook } from "../testing/renderHook";
import type { SceneSource, TargetChange } from "./source";
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
// Its day's heating target raised from its first day's 7 h on (#274).
const WARMER: TargetChange = { timeS: 25_200, target: "heating_day", valueC: 24 };

interface Props {
  source: SceneSource;
  sceneLoading: boolean;
}

/** The hook over a view whose source changes as the hook changes it, each
 * change kept, in order. */
function session({
  source = AT_NOON,
  applyLayout,
}: {
  source?: SceneSource;
  applyLayout?: (layout: string) => Promise<string | null>;
} = {}) {
  const changes: SceneSource[] = [];
  let props: Props = { source, sceneLoading: false };
  let hook: RenderedHook<Props, MoveSessionControls> | null = null;
  const setSource = (change: SetSource) => {
    const next = typeof change === "function" ? change(props.source) : change;
    changes.push(next);
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
        applyLayout,
        sceneLoading,
      }),
    props,
  );
  const rendered = hook;
  return {
    hook: rendered,
    changes,
    /** The view as it is next drawn: another source, or the scene arrived. */
    show(next: Partial<Props>) {
      props = { ...props, ...next };
      rendered.rerender(props);
    },
  };
}

describe("a Move session", () => {
  let current: { hook: RenderedHook<Props, MoveSessionControls> } | undefined;
  // Nothing a session does asks the simulator: the view does, for the source
  // it changes.
  const fetchFn = vi.fn();
  beforeEach(() => vi.stubGlobal("fetch", fetchFn));
  afterEach(() => {
    current?.hook.unmount();
    fetchFn.mockReset();
    vi.unstubAllGlobals();
  });

  it("holds its moves as a draft, and asks the simulator for nothing", () => {
    const view = session();
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
    // No run played back is started over (P22.3): the view's change is all.
    expect(fetchFn).not.toHaveBeenCalled();
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

  it("in a replay, makes a fork in their layout and leaves the view on the run replayed", async () => {
    const applyLayout = vi.fn(async () => null);
    const view = session({ applyLayout });
    current = view;
    act(() => view.hook.current.start());
    act(() => view.hook.current.move("heater", { dx: -1, dy: 0.5 }));

    await act(async () => view.hook.current.apply());

    expect(applyLayout).toHaveBeenCalledWith("default~heater:-1:0.5");
    expect(view.changes).toEqual([]);
    // The page goes to the fork: the moves stay drawn until then.
    expect(view.hook.current.session).toMatchObject({ applying: true, failure: null });
  });

  it("in a replay, keeps its moves and says why, if the fork is refused", async () => {
    const view = session({ applyLayout: async () => "its crop is another" });
    current = view;
    act(() => view.hook.current.start());
    act(() => view.hook.current.move("heater", { dx: -1, dy: 0.5 }));

    await act(async () => view.hook.current.apply());

    expect(view.changes).toEqual([]);
    expect(view.hook.current.session).toMatchObject({
      applying: false,
      to: "default~heater:-1:0.5",
      failure: "its crop is another",
    });
  });

  it("keeps the run's target changes in its new run (decision 0049)", async () => {
    const view = session({ source: { ...AT_NOON, targets: [WARMER] } });
    current = view;
    act(() => view.hook.current.start());
    act(() => view.hook.current.move("heater", { dx: -1, dy: 0.5 }));

    await act(async () => view.hook.current.apply());

    expect(view.changes).toEqual([
      {
        kind: "scenario",
        scenarioId: "climate_box",
        field: "climate",
        targets: [WARMER],
        layout: "default~heater:-1:0.5",
      },
    ]);
  });
});
