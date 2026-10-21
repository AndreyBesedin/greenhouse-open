import { type DependencyList, useEffect, useMemo, useRef } from "react";

/** Something the renderer keeps resources for until it is disposed, such as
 * a Three.js geometry. */
export interface Disposable {
  dispose(): void;
}

function disposeIt(made: Disposable): void {
  made.dispose();
}

/**
 * What `make` makes, made again when `deps` change, and released (by
 * default, disposed) once nothing draws it: a task after it is made again,
 * or after the component leaves.
 *
 * Not in an effect's cleanup alone: in development, React's strict mode runs
 * a new component's effect cleanups and then its effects again, while what
 * it made is still drawn. Three.js (0.186) never draws again a geometry
 * disposed in the frame after the shadow map was drawn, until its program
 * changes, so the crop vanished under the sun as each day's plants arrived
 * (#269). A release therefore waits a task, and is called off if the effect
 * comes back to the same thing.
 */
export function useDisposable<T>(
  make: () => T,
  deps: DependencyList,
  release: (made: T) => void = disposeIt as (made: T) => void,
): T {
  // biome-ignore lint/correctness/useExhaustiveDependencies: the caller's dependencies, as useMemo takes them.
  const made = useMemo(make, deps);
  const leaving = useRef<{ made: T; timer: ReturnType<typeof setTimeout> } | null>(null);
  // A release goes with what it releases: a new one alone makes nothing anew.
  // biome-ignore lint/correctness/useExhaustiveDependencies: `release` is read with `made`.
  useEffect(() => {
    if (leaving.current?.made === made) {
      clearTimeout(leaving.current.timer);
    }
    leaving.current = null;
    return () => {
      leaving.current = { made, timer: setTimeout(() => release(made), 0) };
    };
  }, [made]);
  return made;
}
