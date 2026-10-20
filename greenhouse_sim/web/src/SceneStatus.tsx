import type { SceneSource, SceneState } from "./scene/source";

/** What a source draws; a scenario's scene is before its first day, unless
 * its crop is drawn on a later one (`day`). */
function describeSource(source: SceneSource, day = 0): string {
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
      return source.layout === undefined
        ? `scenario ${source.scenarioId}${when}`
        : `scenario ${source.scenarioId} with its ${source.layout} layout${when}`;
    }
    case "live":
      return `scenario ${source.scenarioId}, live`;
  }
}

/** What is drawn, and if a scene could not be drawn, exactly why: one line,
 * the "Show" chooser's while it is folded (#201), so that it says what is
 * shown, or why nothing is, as it stands open or not. */
export function SceneStatus({ source, state }: { source: SceneSource; state: SceneState }) {
  switch (state.status) {
    case "none":
      return <span data-testid="scene-status">Showing the {describeSource(source)}.</span>;
    case "loading":
      return <span data-testid="scene-status">Loading the {describeSource(source)}…</span>;
    case "unavailable":
      return (
        <span data-testid="scene-status" role="alert">
          The {describeSource(source)} is not available: {state.reason}.
        </span>
      );
    case "rejected":
      return (
        <span data-testid="scene-status" role="alert">
          The {describeSource(source)} was rejected: {state.problems.join("; ")}.
        </span>
      );
    case "loaded":
      return (
        <span data-testid="scene-status">
          Showing the {describeSource(source, state.snapshot.simulated_day)}:{" "}
          {state.snapshot.greenhouse_id}, day {state.snapshot.simulated_day},{" "}
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
