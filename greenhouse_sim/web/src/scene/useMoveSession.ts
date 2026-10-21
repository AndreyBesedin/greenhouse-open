import { useCallback, useEffect, useState } from "react";

import { withTime } from "./edits";
import { layoutWith, movedBy, type Offset, putBack, sameLayout } from "./moves";
import { commandPlayback, type PlaybackLoad } from "./playback";
import type { SceneSource } from "./source";
import type { SetSource } from "./useSource";

/** A Move session (#209, #271): the scenario's layout it started from, and
 * the layout its moves make, a draft drawn over the scene and asked of the
 * simulator only once it is applied; whether it is being applied, the run
 * played back starting over with it or its scene on its way; and why the
 * run played back could not start over with it, if it could not. */
export interface MoveSession {
  scenarioId: string;
  from: string | undefined;
  to: string | undefined;
  applying: boolean;
  failure: string | null;
}

/** A Move session, and what can be done with it. */
export interface MoveSessionControls {
  session: MoveSession | null;
  /** Whether applying it would change the run drawn. */
  changed: boolean;
  start: () => void;
  /** An item dropped, moved by `by` from where the session draws it. */
  move: (item: string, by: Offset) => void;
  /** An item back where its layout places it. */
  putBack: (item: string) => void;
  /** Every item back where its layout places it. */
  putEverythingBack: () => void;
  apply: () => Promise<void>;
  cancel: () => void;
}

/** A scenario's view with another layout, or with its own (undefined). */
function withLayout(source: SceneSource, layout: string | undefined): SceneSource {
  if (source.kind !== "scenario") {
    return source;
  }
  const { layout: _, ...rest } = source;
  return layout === undefined ? rest : { ...rest, layout };
}

/**
 * A Move session over the scenario's view `source` (#271). It starts from
 * the layout drawn; its moves are a draft, which nothing asks the simulator
 * for. Applied, it asks for the layout they make all at once, at the run's
 * start (0 s), in one change of the source, so one page of the browser's
 * history: Back takes it back. While the view follows the run played back
 * (`followed`), the playback starts over with that layout first, as a new
 * run from its first day, and the view follows it; if it cannot, the
 * session stays, saying why. Cancelled, or once the view shows another
 * scenario or layout, as Back does, the draft is let go. Applied, it lasts
 * until the scene with its moves has arrived (`sceneLoading` no longer), so
 * that the items stay drawn where they were dropped meanwhile.
 */
export function useMoveSession({
  source,
  setSource,
  defaultLayout,
  followed,
  onPlayback,
  sceneLoading,
  fetchFn = fetch,
}: {
  source: SceneSource;
  setSource: (change: SetSource) => void;
  defaultLayout: string;
  followed: string | null;
  onPlayback: (load: PlaybackLoad) => void;
  sceneLoading: boolean;
  fetchFn?: typeof fetch;
}): MoveSessionControls {
  const [session, setSession] = useState<MoveSession | null>(null);
  const scenarioId = source.kind === "scenario" ? source.scenarioId : null;
  const layout = source.kind === "scenario" ? source.layout : undefined;
  const here = session !== null && scenarioId === session.scenarioId;
  const ended =
    session !== null &&
    (session.applying
      ? here && layout === session.to && !sceneLoading
      : !here || layout !== session.from);
  useEffect(() => {
    if (ended) {
      setSession(null);
    }
  }, [ended]);
  const live = ended ? null : session;

  const drafting = (change: (to: string | undefined) => string | undefined) =>
    setSession((was) => (was === null || was.applying ? was : { ...was, to: change(was.to) }));
  const start = useCallback(() => {
    if (scenarioId !== null) {
      setSession({ scenarioId, from: layout, to: layout, applying: false, failure: null });
    }
  }, [scenarioId, layout]);
  const cancel = useCallback(
    () => setSession((was) => (was === null || was.applying ? was : null)),
    [],
  );
  async function apply(): Promise<void> {
    if (live === null || live.applying) {
      return;
    }
    const { to } = live;
    setSession({ ...live, applying: true, failure: null });
    if (followed !== null) {
      const restarted = await commandPlayback(followed, "restart", fetchFn, to ?? defaultLayout);
      onPlayback(restarted);
      if (restarted.status !== "loaded") {
        const failure = restarted.status === "unavailable" ? restarted.reason : "no answer";
        setSession((was) => was && { ...was, applying: false, failure });
        return;
      }
    }
    setSource((current) =>
      current.kind === "scenario" ? withLayout(withTime(current, 0), to) : current,
    );
  }
  return {
    session: live,
    changed: live !== null && !sameLayout(live.from, live.to, defaultLayout),
    start,
    move: (item, by) => drafting((to) => movedBy(to, defaultLayout, item, by)),
    putBack: (item) => drafting((to) => putBack(to, defaultLayout, item)),
    putEverythingBack: () => drafting((to) => layoutWith(to, defaultLayout, {})),
    apply,
    cancel,
  };
}
