import { useEffect, useEffectEvent, useState } from "react";

/** An answer on its way. */
export type Loading = { status: "loading" };
/** Nothing asked for, or an answer on its way. */
export type Pending = { status: "none" } | Loading;

const NONE: Pending = { status: "none" };
const LOADING: Loading = { status: "loading" };

type Settled = { status: string };

interface Answer<T> {
  key: string;
  group: string;
  state: T;
}

interface Options<R, T> {
  /** What names a request: two requests with the same key are the same. */
  key?: ((request: R) => string) | undefined;
  /** A loaded answer stays on show while the next loads only within its
   * group; any other change starts from loading. */
  group?: string | undefined;
  /** Acts on an answer as it arrives, with the render that shows it. */
  onAnswer?: ((state: T) => void) | undefined;
  /** The fetch that the one given to the load cancels: the browser's,
   * unless another is given, as a test gives its own. */
  fetch?: typeof fetch | undefined;
}

/** Loads what a request asks for, through `fetchFn`: a `fetch` that gives
 * up once the request is no longer wanted. */
type Load<R, T> = (request: R, fetchFn: typeof fetch) => Promise<T>;

/**
 * What `load` answers for `request`, asked for again whenever the request
 * changes; `null` asks for nothing. A request is its address, unless
 * `options.key` names it.
 *
 * An answer that loaded stays on show until the next arrives; anything else
 * gives way to loading. A request that has changed, or whose component has
 * gone, is given up: what `load` fetches for it is cancelled, so that it
 * holds none of the browser's few connections to the API, and an answer
 * that arrives anyway is dropped.
 */
export function useLoad<T extends Settled>(
  url: string,
  load: Load<string, T>,
  options?: Options<string, T>,
): T | Loading;
export function useLoad<T extends Settled>(
  url: string | null,
  load: Load<string, T>,
  options?: Options<string, T>,
): T | Pending;
export function useLoad<R, T extends Settled>(
  request: R | null,
  load: Load<R, T>,
  options: Options<R, T> & { key: (request: R) => string },
): T | Pending;
export function useLoad<R, T extends Settled>(
  request: R | null,
  load: Load<R, T>,
  options: Options<R, T> = {},
): T | Pending {
  const key = request === null ? null : (options.key ?? String)(request);
  const group = options.group ?? "";
  const [answer, setAnswer] = useState<Answer<T> | null>(null);
  const ask = useEffectEvent((signal: AbortSignal) => {
    if (request === null) {
      return null;
    }
    const fetching = options.fetch ?? fetch;
    return load(request, (input, init) => fetching(input, { ...init, signal }));
  });
  const answered = useEffectEvent((state: T) => options.onAnswer?.(state));

  useEffect(() => {
    if (key === null) {
      // Asked for again later, it starts from loading.
      setAnswer(null);
      return;
    }
    let current = true;
    const wanted = new AbortController();
    void ask(wanted.signal)?.then(
      (state) => {
        if (current) {
          setAnswer({ key, group, state });
          answered(state);
        }
      },
      (error: unknown) => {
        // A load given up may fail as it gives up; any other failure is
        // its own to report.
        if (current) {
          throw error;
        }
      },
    );
    return () => {
      current = false;
      wanted.abort();
    };
  }, [key, group]);

  if (key === null) {
    return NONE;
  }
  if (answer === null) {
    return LOADING;
  }
  if (answer.key === key && answer.group === group) {
    return answer.state;
  }
  return answer.state.status === "loaded" && answer.group === group ? answer.state : LOADING;
}
