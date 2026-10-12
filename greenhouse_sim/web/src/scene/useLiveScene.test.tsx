// @vitest-environment jsdom
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { renderHook } from "../testing/renderHook";
import type { SceneSnapshot } from "./generated/snapshotTypes";
import { type LiveFrame, liveUrl } from "./live";
import { useLiveScene } from "./useLiveScene";

// Read by its path: the DOM environment's URL is not one Node's files take.
const EXAMPLE: SceneSnapshot = JSON.parse(
  readFileSync(
    resolve(dirname(fileURLToPath(import.meta.url)), "../../public/scenes/example.json"),
    "utf8",
  ),
);
const FRAME: LiveFrame = {
  sequence: 3,
  day: 2,
  timestamp: "2026-01-03T12:00:00Z",
  playing: true,
  speed: 1,
  snapshot: EXAMPLE,
};
const RECONNECT_AFTER_MS = 1000;

/** A stream the test drives: it opens, sends frames and fails when told. */
class FakeEventSource {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;
  static opened: FakeEventSource[] = [];

  readyState = FakeEventSource.CONNECTING;
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  private readonly frames: ((event: MessageEvent<string>) => void)[] = [];

  constructor(readonly url: string) {
    FakeEventSource.opened.push(this);
  }

  addEventListener(type: string, listener: (event: MessageEvent<string>) => void): void {
    if (type === "frame") {
      this.frames.push(listener);
    }
  }

  close(): void {
    this.readyState = FakeEventSource.CLOSED;
  }

  open(): void {
    act(() => {
      this.readyState = FakeEventSource.OPEN;
      this.onopen?.();
    });
  }

  send(data: string): void {
    act(() => {
      for (const listener of this.frames) {
        listener(new MessageEvent("frame", { data }));
      }
    });
  }

  /** An error the browser gives up on (closed), or one it retries itself. */
  fail(givenUp: boolean): void {
    act(() => {
      this.readyState = givenUp ? FakeEventSource.CLOSED : FakeEventSource.CONNECTING;
      this.onerror?.();
    });
  }
}

function stream(at: number): FakeEventSource {
  const opened = FakeEventSource.opened[at];
  if (opened === undefined) {
    throw new Error(`no stream ${at} was opened`);
  }
  return opened;
}

function wait(ms: number): void {
  act(() => {
    vi.advanceTimersByTime(ms);
  });
}

describe("following a scenario's live stream", () => {
  beforeEach(() => {
    FakeEventSource.opened = [];
    vi.stubGlobal("EventSource", FakeEventSource);
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("opens no stream without a scenario", () => {
    const hook = renderHook(useLiveScene, null);

    expect(FakeEventSource.opened).toHaveLength(0);
    expect(hook.current.scene).toEqual({ status: "none" });
  });

  it("is connecting and loading until the scenario's first frame arrives", () => {
    const hook = renderHook(useLiveScene, "climate_box");
    expect(stream(0).url).toBe(liveUrl("climate_box"));
    expect(hook.current).toEqual({
      connection: "connecting",
      frame: null,
      scene: { status: "loading" },
    });

    stream(0).open();
    stream(0).send(JSON.stringify(FRAME));

    expect(hook.current).toEqual({
      connection: "live",
      frame: FRAME,
      scene: { status: "loaded", snapshot: EXAMPLE },
    });
  });

  it("shows a frame it refuses, and recovers with the next good one", () => {
    const hook = renderHook(useLiveScene, "climate_box");

    stream(0).send("not json");
    expect(hook.current.scene).toEqual({
      status: "rejected",
      problems: ["the frame is not JSON"],
    });
    stream(0).send(JSON.stringify(FRAME));

    expect(hook.current.scene).toEqual({ status: "loaded", snapshot: EXAMPLE });
  });

  it("closes the old stream when the scenario changes, and starts the new one afresh", () => {
    const hook = renderHook(useLiveScene, "climate_box");
    stream(0).send(JSON.stringify(FRAME));

    hook.rerender("gh_001");

    expect(stream(0).readyState).toBe(FakeEventSource.CLOSED);
    expect(stream(1).url).toBe(liveUrl("gh_001"));
    expect(hook.current).toEqual({
      connection: "connecting",
      frame: null,
      scene: { status: "loading" },
    });
  });

  it("tries again a second after the browser gives up, and not before", () => {
    const hook = renderHook(useLiveScene, "climate_box");

    stream(0).fail(true);
    expect(hook.current.connection).toBe("disconnected");
    wait(RECONNECT_AFTER_MS - 1);
    expect(FakeEventSource.opened).toHaveLength(1);
    wait(1);

    expect(stream(1).url).toBe(liveUrl("climate_box"));
    stream(1).send(JSON.stringify(FRAME));
    expect(hook.current.connection).toBe("live");
  });

  it("leaves a stream the browser is retrying to the browser", () => {
    const hook = renderHook(useLiveScene, "climate_box");

    stream(0).fail(false);
    wait(RECONNECT_AFTER_MS * 5);

    expect(hook.current.connection).toBe("disconnected");
    expect(FakeEventSource.opened).toHaveLength(1);
  });

  it("closes its stream when it goes, and cancels a retry still waiting", () => {
    const hook = renderHook(useLiveScene, "climate_box");
    stream(0).fail(true);

    hook.unmount();
    wait(RECONNECT_AFTER_MS * 2);

    expect(FakeEventSource.opened).toHaveLength(1);
  });

  it("cancels a waiting retry when the scenario changes", () => {
    const hook = renderHook(useLiveScene, "climate_box");
    stream(0).fail(true);

    hook.rerender("gh_001");
    wait(RECONNECT_AFTER_MS * 2);

    expect(FakeEventSource.opened.map((opened) => opened.url)).toEqual([
      liveUrl("climate_box"),
      liveUrl("gh_001"),
    ]);
  });
});
