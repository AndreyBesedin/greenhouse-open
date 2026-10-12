import { act } from "react";
import { createRoot } from "react-dom/client";

declare global {
  // React checks it to know that updates are awaited with act().
  var IS_REACT_ACT_ENVIRONMENT: boolean | undefined;
}

export interface RenderedHook<P, R> {
  /** What the hook returned on its latest render. */
  readonly current: R;
  /** Renders it again with other props. */
  rerender(props: P): void;
  /** Unmounts the component it runs in. */
  unmount(): void;
}

/**
 * Runs a hook in a mounted component, for tests in a DOM environment
 * (`// @vitest-environment jsdom`), so that its effects, subscriptions and
 * clean-ups run as in the viewer. Answers it is waiting for arrive inside
 * `await act(async () => ...)`.
 */
export function renderHook<P, R>(hook: (props: P) => R, props: NoInfer<P>): RenderedHook<P, R> {
  globalThis.IS_REACT_ACT_ENVIRONMENT = true;
  let latest: { result: R } | null = null;
  function Probe({ given }: { given: P }) {
    latest = { result: hook(given) };
    return null;
  }
  const root = createRoot(document.createElement("div"));
  act(() => root.render(<Probe given={props} />));
  return {
    get current(): R {
      if (latest === null) {
        throw new Error("the hook has not rendered");
      }
      return latest.result;
    },
    rerender(next: P) {
      act(() => root.render(<Probe given={next} />));
    },
    unmount() {
      act(() => root.unmount());
    },
  };
}
