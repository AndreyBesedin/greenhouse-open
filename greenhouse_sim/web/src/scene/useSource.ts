import { useEffect, useRef, useState } from "react";

import { qaModeFrom, withQaMode } from "../qaMode/mode";
import { type SceneSource, searchFor, shownBy, sourceFromSearch } from "./source";

/**
 * The scene's source, and how to change it: read from the address once, and
 * kept in it. The address follows every change once it is made, so that a
 * refresh, or the address shared, opens the same view; only QA mode's part
 * of it (`useQaMode`) is written apart, and kept. The address the page was
 * opened at stays as it was until the first change.
 *
 * Another scene, scenario, layout or the plant lab (`shownBy`) is a new page
 * in the browser's history, and Back returns to the view before it, as its
 * address held it (#201); any other change replaces the current page.
 */
export function useSource(): [SceneSource, (change: SetSource) => void] {
  const [source, setSource] = useState<SceneSource>(() => sourceFromSearch(location.search));
  // The source the address holds.
  const addressed = useRef(source);

  useEffect(() => {
    if (source === addressed.current) {
      return;
    }
    const search = withQaMode(searchFor(source), qaModeFrom(location.search));
    const address = `${location.pathname}${search}`;
    if (shownBy(source) === shownBy(addressed.current)) {
      history.replaceState(null, "", address);
    } else {
      history.pushState(null, "", address);
    }
    addressed.current = source;
  }, [source]);

  useEffect(() => {
    const returned = () => {
      const restored = sourceFromSearch(location.search);
      addressed.current = restored;
      setSource(restored);
    };
    window.addEventListener("popstate", returned);
    return () => window.removeEventListener("popstate", returned);
  }, []);

  return [source, setSource];
}

/** Another source, or a change to the current one. */
export type SetSource = SceneSource | ((current: SceneSource) => SceneSource);
