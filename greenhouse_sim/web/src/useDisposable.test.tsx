// @vitest-environment jsdom
import { act, StrictMode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useDisposable } from "./useDisposable";

/** A geometry's stand-in: it counts its disposals. */
class Made {
  disposed = 0;
  constructor(readonly name: string) {}
  dispose(): void {
    this.disposed += 1;
  }
}

/** Renders a component that makes a `Made` named `name`, in strict mode as
 * the viewer's development build runs, and keeps what it last returned. */
function mount(name: string): { root: Root; latest: () => Made; show: (next: string) => void } {
  let latest: Made | null = null;
  function Maker({ named }: { named: string }) {
    latest = useDisposable(() => new Made(named), [named]);
    return null;
  }
  const root = createRoot(document.createElement("div"));
  const show = (next: string) =>
    act(() =>
      root.render(
        <StrictMode>
          <Maker named={next} />
        </StrictMode>,
      ),
    );
  show(name);
  return {
    root,
    latest: () => {
      if (latest === null) {
        throw new Error("nothing was made");
      }
      return latest;
    },
    show,
  };
}

describe("what a component makes and the renderer draws", () => {
  beforeEach(() => {
    globalThis.IS_REACT_ACT_ENVIRONMENT = true;
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("is kept while it is drawn, though strict mode runs the effect's cleanup on mounting (#269)", () => {
    const { latest } = mount("leaf");
    vi.runAllTimers();

    expect(latest().disposed).toBe(0);
  });

  it("is disposed once, a task after the component leaves", () => {
    const { root, latest } = mount("leaf");
    const made = latest();
    act(() => root.unmount());

    expect(made.disposed).toBe(0);
    vi.runAllTimers();
    expect(made.disposed).toBe(1);
  });

  it("is made again when what it is made from changes, and the one it replaced disposed", () => {
    const { latest, show } = mount("leaf");
    const first = latest();
    show("stem");
    vi.runAllTimers();

    expect(latest().name).toBe("stem");
    expect(first.disposed).toBe(1);
    expect(latest().disposed).toBe(0);
  });

  it("is released as the caller says, when it is not itself disposable", () => {
    const released: string[] = [];
    function Lines() {
      useDisposable(
        () => ({ geometry: "lines", material: "dashes" }),
        [],
        (made) => released.push(made.geometry, made.material),
      );
      return null;
    }
    const root = createRoot(document.createElement("div"));
    act(() =>
      root.render(
        <StrictMode>
          <Lines />
        </StrictMode>,
      ),
    );
    vi.runAllTimers();
    expect(released).toEqual([]);

    act(() => root.unmount());
    vi.runAllTimers();
    expect(released).toEqual(["lines", "dashes"]);
  });
});
