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
}

/**
 * What `load` answers for `request`, asked for again whenever the request
 * changes; `null` asks for nothing. A request is its address, unless
 * `options.key` names it.
 *
 * An answer that loaded stays on show until the next arrives; anything else
 * gives way to loading. An answer that arrives after the request has
 * changed, or after the component has gone, is dropped.
 */
export function useLoad<T extends Settled>(
  url: string,
  load: (url: string) => Promise<T>,
  options?: Options<string, T>,
): T | Loading;
export function useLoad<T extends Settled>(
  url: string | null,
  load: (url: string) => Promise<T>,
  options?: Options<string, T>,
): T | Pending;
export function useLoad<R, T extends Settled>(
  request: R | null,
  load: (request: R) => Promise<T>,
  options: Options<R, T> & { key: (request: R) => string },
): T | Pending;
export function useLoad<R, T extends Settled>(
  request: R | null,
  load: (request: R) => Promise<T>,
  options: Options<R, T> = {},
): T | Pending {
  const key = request === null ? null : (options.key ?? String)(request);
  const group = options.group ?? "";
  const [answer, setAnswer] = useState<Answer<T> | null>(null);
  const ask = useEffectEvent(() => (request === null ? null : load(request)));
  const answered = useEffectEvent((state: T) => options.onAnswer?.(state));

  useEffect(() => {
    if (key === null) {
      // Asked for again later, it starts from loading.
      setAnswer(null);
      return;
    }
    let current = true;
    void ask()?.then((state) => {
      if (current) {
        setAnswer({ key, group, state });
        answered(state);
      }
    });
    return () => {
      current = false;
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
