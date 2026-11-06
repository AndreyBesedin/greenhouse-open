import { dayCount } from "./clock";
import { DEFAULT_LAYOUT } from "./scenarios";
import { baseLayout, movesIn } from "./scene/moves";
import type { SceneState } from "./scene/sceneLoad";
import type { SceneSource } from "./scene/source";

/** What a source draws; a scenario's scene is before its first day, unless
 * its crop is drawn some days in (`day`, the days it has lived), and null
 * says nothing of its day, as of a scene that could not be drawn. */
function describeSource(source: SceneSource, day: number | null = 0): string {
  switch (source.kind) {
    case "reference":
      return "empty grid";
    case "example":
      return "example scene";
    case "fixtures":
      return "fixture gallery";
    case "plants":
      return "plant lab";
    case "stress":
      return `stress scene of ${source.plants} plants`;
    case "scenario": {
      const when = day === 0 ? ", before day one" : "";
      // A layout with moves is its base with them (#209).
      const base = baseLayout(source.layout);
      const moved = Object.keys(movesIn(source.layout)).sort();
      const layout =
        base === undefined || base === DEFAULT_LAYOUT ? "" : ` with its ${base} layout`;
      const moves = moved.length === 0 ? "" : `, ${moved.join(", ")} moved`;
      return `scenario ${source.scenarioId}${layout}${moves}${when}`;
    }
  }
}

/** What is drawn, and if a scene could not be drawn, exactly why: one line in
 * the "Show" chooser's summary (#201). A person sees it when it has
 * something to tell: a scene on its way, or one that could not be drawn.
 * What is drawn is already in front of them, so that line is not shown; it
 * is still announced, politely, for whoever hears the page, and read by the
 * tests. */
export function SceneStatus({ source, state }: { source: SceneSource; state: SceneState }) {
  switch (state.status) {
    case "none":
      return (
        <span data-testid="scene-status" role="status" className="visually-hidden">
          Showing the {describeSource(source)}.
        </span>
      );
    case "loading":
      return <span data-testid="scene-status">Loading the {describeSource(source)}…</span>;
    case "unavailable":
      return (
        <span data-testid="scene-status" role="alert">
          The {describeSource(source, null)} is not available: {state.reason}.
        </span>
      );
    case "rejected":
      return (
        <span data-testid="scene-status" role="alert">
          The {describeSource(source, null)} was rejected: {state.problems.join("; ")}.
        </span>
      );
    case "loaded":
      return (
        <span data-testid="scene-status" role="status" className="visually-hidden">
          Showing the {describeSource(source, state.snapshot.simulated_day)}:{" "}
          {state.snapshot.greenhouse_id}, {dayCount(state.snapshot.simulated_day)} in,{" "}
          {state.snapshot.entities.length} entities.
        </span>
      );
  }
}

/** What failed to arrive while something else is drawn in its place, so
 * that it is never taken for what was asked for (#197). */
export function SceneFailures({ failures }: { failures: readonly string[] }) {
  if (failures.length === 0) {
    return null;
  }
  return (
    <p data-testid="scene-failures" role="alert">
      Not drawn as asked: {failures.join("; ")}.
    </p>
  );
}
