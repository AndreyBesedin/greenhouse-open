import { useEffect, useRef, useState } from "react";

import { type SceneSource, searchFor, sourceFromSearch } from "./source";

/**
 * The scene's source, and how to change it: read from the address once, and
 * kept in it. The address follows every change once it is made, so that a
 * refresh, or the address shared, opens the same view; nothing else writes
 * it. The address the page was opened at stays as it was until the first
 * change.
 */
export function useSource(): [SceneSource, (change: SetSource) => void] {
  const [source, setSource] = useState<SceneSource>(() => sourceFromSearch(location.search));
  const opened = useRef(source);

  useEffect(() => {
    if (source !== opened.current) {
      history.replaceState(null, "", `${location.pathname}${searchFor(source)}`);
    }
  }, [source]);

  return [source, setSource];
}

/** Another source, or a change to the current one. */
export type SetSource = SceneSource | ((current: SceneSource) => SceneSource);
