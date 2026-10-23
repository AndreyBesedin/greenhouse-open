import { useEffect, useEffectEvent, useState } from "react";

/** An answer on its way. */
export type Loading = { status: "loading" };
/** Nothing asked for, or an answer on its way. */
export type Pending = { status: "none" } | Loading;

const NONE: Pending = { status: "none" };
const LOADING: Loading = { status: "loading" };

type Settled = { status: string };
/** An answer that loaded. */
type Loaded<T extends Settled> = Extract<T, { status: "loaded" }>;

interface Answer<T> {
  key: string;
  group: string;
  state: T;
}

/** What a load has on show, and how its latest request stands apart from
 * it (`useLoadProgress`). */
export interface Progress<T extends Settled> {
  /** The latest answer that loaded within the request's group, on show
   * while the next loads and when the next fails; null if none has. */
  shown: Loaded<T> | null;
  /** The latest request's own answer, or how it stands until it arrives. */
  latest: T | Pending;
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
  const { key, group, answer } = useAnswers(request, load, options);
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

/**
 * What `load` answers for `url`, asked for as `useLoad` asks, told apart:
 * what is on show, which is the latest answer that loaded within the
 * group, kept while the next loads and also when the next fails; and how
 * the latest request stands, so that what is on show is never taken for
 * the answer to a request still on its way, or one that failed.
 */
export function useLoadProgress<T extends Settled>(
  url: string | null,
  load: Load<string, T>,
  options?: Options<string, T>,
): Progress<T> {
  const { key, group, answer, loaded } = useAnswers(url, load, options);
  if (key === null) {
    return { shown: null, latest: NONE };
  }
  return {
    shown: loaded !== null && loaded.group === group ? loaded.state : null,
    latest:
      answer !== null && answer.key === key && answer.group === group ? answer.state : LOADING,
  };
}

function isLoaded<T extends Settled>(state: T): state is Loaded<T> {
  return state.status === "loaded";
}

/** The latest answer to a request, and the latest that loaded, each with
 * the request and the group it answers; asked for again whenever the
 * request or its group changes. */
function useAnswers<R, T extends Settled>(
  request: R | null,
  load: Load<R, T>,
  options: Options<R, T> = {},
): {
  key: string | null;
  group: string;
  answer: Answer<T> | null;
  loaded: Answer<Loaded<T>> | null;
} {
  const key = request === null ? null : (options.key ?? String)(request);
  const group = options.group ?? "";
  const [answer, setAnswer] = useState<Answer<T> | null>(null);
  const [loaded, setLoaded] = useState<Answer<Loaded<T>> | null>(null);
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
      setLoaded(null);
      return;
    }
    let current = true;
    const wanted = new AbortController();
    void ask(wanted.signal)?.then(
      (state) => {
        if (current) {
          setAnswer({ key, group, state });
          if (isLoaded(state)) {
            setLoaded({ key, group, state });
          }
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

  return { key, group, answer, loaded };
}

/** What a part of the view draws: the latest of it that loaded, kept while
 * the next is on its way and when the next fails, or else how its latest
 * request stands. */
export function drawn<T extends Settled>({ shown, latest }: Progress<T>): T | Pending {
  return shown ?? latest;
}

/** Whether a part's latest request failed. */
export function failed(latest: Settled): boolean {
  return latest.status === "unavailable" || latest.status === "rejected";
}

/** Why a part's latest request failed, in words, if it did. */
export function failureOf(part: string, latest: Settled): string | null {
  if (latest.status === "unavailable" && "reason" in latest) {
    return `the ${part} is not available (${String(latest.reason)})`;
  }
  if (latest.status === "rejected" && "problems" in latest && Array.isArray(latest.problems)) {
    return `the ${part} was refused (${latest.problems.join("; ")})`;
  }
  return null;
}
