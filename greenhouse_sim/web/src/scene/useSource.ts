import { useEffect, useRef, useState } from "react";

import { qaModeFrom, withQaMode } from "../qaMode/mode";
import { type SceneSource, searchFor, sourceFromSearch } from "./source";

/**
 * The scene's source, and how to change it: read from the address once, and
 * kept in it. The address follows every change once it is made, so that a
 * refresh, or the address shared, opens the same view; only QA mode's part
 * of it (`useQaMode`) is written apart, and kept. The address the page was
 * opened at stays as it was until the first change.
 */
export function useSource(): [SceneSource, (change: SetSource) => void] {
  const [source, setSource] = useState<SceneSource>(() => sourceFromSearch(location.search));
  const opened = useRef(source);

  useEffect(() => {
    if (source !== opened.current) {
      const search = withQaMode(searchFor(source), qaModeFrom(location.search));
      history.replaceState(null, "", `${location.pathname}${search}`);
    }
  }, [source]);

  return [source, setSource];
}

/** Another source, or a change to the current one. */
export type SetSource = SceneSource | ((current: SceneSource) => SceneSource);
