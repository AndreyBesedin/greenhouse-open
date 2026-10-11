// @vitest-environment jsdom
import { act } from "react";
import { describe, expect, it, vi } from "vitest";

import { renderHook } from "./testing/renderHook";
import { useLoad } from "./useLoad";

type State = { status: "loaded"; value: string } | { status: "unavailable"; reason: string };

/** A load whose answers arrive when the test says, one per request. */
function answering() {
  const waiting = new Map<string, (state: State) => void>();
  const load = vi.fn(
    (url: string) =>
      new Promise<State>((resolve) => {
        waiting.set(url, resolve);
      }),
  );
  async function answer(url: string, state: State): Promise<void> {
    const resolve = waiting.get(url);
    if (resolve === undefined) {
      throw new Error(`nothing asked for ${url}`);
    }
    await act(async () => resolve(state));
  }
  return { load, answer };
}

function loaded(value: string): State {
  return { status: "loaded", value };
}

interface Props {
  url: string | null;
  group?: string;
  onAnswer?: (state: State) => void;
}

describe("loading what a request names", () => {
  it("asks for nothing without a request", () => {
    const { load } = answering();
    const hook = renderHook(({ url }: Props) => useLoad(url, load), { url: null });

    expect(hook.current).toEqual({ status: "none" });
    expect(load).not.toHaveBeenCalled();
  });

  it("is loading until the answer arrives, and then shows it", async () => {
    const { load, answer } = answering();
    const hook = renderHook(({ url }: Props) => useLoad(url, load), { url: "/a" });

    expect(hook.current).toEqual({ status: "loading" });
    await answer("/a", loaded("A"));

    expect(hook.current).toEqual(loaded("A"));
    expect(load).toHaveBeenCalledExactlyOnceWith("/a");
  });

  it("keeps a loaded answer on show while the next request loads", async () => {
    const { load, answer } = answering();
    const hook = renderHook(({ url }: Props) => useLoad(url, load), { url: "/a" });
    await answer("/a", loaded("A"));

    hook.rerender({ url: "/b" });
    expect(hook.current).toEqual(loaded("A"));
    await answer("/b", loaded("B"));

    expect(hook.current).toEqual(loaded("B"));
  });

  it("shows loading in place of an answer that did not load", async () => {
    const { load, answer } = answering();
    const hook = renderHook(({ url }: Props) => useLoad(url, load), { url: "/a" });
    await answer("/a", { status: "unavailable", reason: "the API answered 500" });

    hook.rerender({ url: "/b" });

    expect(hook.current).toEqual({ status: "loading" });
  });

  it("drops an answer to a request since changed, whichever arrives first", async () => {
    const { load, answer } = answering();
    const hook = renderHook(({ url }: Props) => useLoad(url, load), { url: "/a" });
    hook.rerender({ url: "/b" });

    await answer("/b", loaded("B"));
    await answer("/a", loaded("A"));

    expect(hook.current).toEqual(loaded("B"));
  });

  it("drops an answer that arrives after the component has gone", async () => {
    const { load, answer } = answering();
    const onAnswer = vi.fn();
    const hook = renderHook(({ url }: Props) => useLoad(url, load, { onAnswer }), { url: "/a" });

    hook.unmount();
    await answer("/a", loaded("A"));

    expect(onAnswer).not.toHaveBeenCalled();
  });

  it("asks again only when the request changes, not when the load does", () => {
    const { load } = answering();
    const hook = renderHook(({ url }: Props) => useLoad(url, (asked) => load(asked)), {
      url: "/a",
    });

    hook.rerender({ url: "/a" });
    hook.rerender({ url: "/a" });

    expect(load).toHaveBeenCalledOnce();
  });

  it("starts from loading when asked again after asking for nothing", async () => {
    const { load, answer } = answering();
    const hook = renderHook(({ url }: Props) => useLoad(url, load), { url: "/a" });
    await answer("/a", loaded("A"));

    hook.rerender({ url: null });
    expect(hook.current).toEqual({ status: "none" });
    hook.rerender({ url: "/a" });

    expect(hook.current).toEqual({ status: "loading" });
    expect(load).toHaveBeenCalledTimes(2);
  });

  it("keeps a loaded answer on show only within its group", async () => {
    const { load, answer } = answering();
    const hook = renderHook(({ url, group }: Props) => useLoad(url, load, { group }), {
      url: "/a",
      group: "one",
    });
    await answer("/a", loaded("A"));

    hook.rerender({ url: "/b", group: "one" });
    expect(hook.current).toEqual(loaded("A"));
    hook.rerender({ url: "/c", group: "two" });

    expect(hook.current).toEqual({ status: "loading" });
  });

  it("acts on an answer once, with the render that shows it", async () => {
    const { load, answer } = answering();
    const shown: string[] = [];
    const hook = renderHook(
      ({ url, onAnswer }: Props) => {
        const state = useLoad(url, load, { onAnswer });
        shown.push(state.status);
        return state;
      },
      { url: "/a", onAnswer: (state) => shown.push(`answered ${state.status}`) },
    );

    await answer("/a", loaded("A"));

    expect(hook.current).toEqual(loaded("A"));
    expect(shown).toEqual(["loading", "answered loaded", "loaded"]);
  });

  it("names a request by its key, so that an equal one is not asked again", async () => {
    const load = vi.fn(async ({ id }: { id: string }): Promise<State> => loaded(id));
    const hook = renderHook(
      ({ id }: { id: string }) => useLoad({ id }, load, { key: (request) => request.id }),
      { id: "a" },
    );
    await act(async () => undefined);

    hook.rerender({ id: "a" });

    expect(hook.current).toEqual(loaded("a"));
    expect(load).toHaveBeenCalledOnce();
  });
});
