import type { SceneSource, SceneState } from "./scene/source";

function describeSource(source: SceneSource): string {
  switch (source.kind) {
    case "reference":
      return "reference scene";
    case "example":
      return "example scene";
    case "fixtures":
      return "fixture gallery";
    case "stress":
      return `stress scene of ${source.plants} plants`;
    case "scenario":
      return source.layout === undefined
        ? `scenario ${source.scenarioId}, before day one`
        : `scenario ${source.scenarioId} with its ${source.layout} layout, before day one`;
    case "live":
      return `scenario ${source.scenarioId}, live`;
  }
}

/** What is drawn, and if a scene could not be drawn, exactly why. */
export function SceneStatus({ source, state }: { source: SceneSource; state: SceneState }) {
  switch (state.status) {
    case "none":
      return <p data-testid="scene-status">Showing the {describeSource(source)}.</p>;
    case "loading":
      return <p data-testid="scene-status">Loading the {describeSource(source)}…</p>;
    case "unavailable":
      return (
        <p data-testid="scene-status" role="alert">
          The {describeSource(source)} is not available: {state.reason}.
        </p>
      );
    case "rejected":
      return (
        <div data-testid="scene-status" role="alert">
          <p>The {describeSource(source)} was rejected:</p>
          <ul>
            {state.problems.map((problem) => (
              <li key={problem}>{problem}</li>
            ))}
          </ul>
        </div>
      );
    case "loaded":
      return (
        <p data-testid="scene-status">
          Showing the {describeSource(source)}: {state.snapshot.greenhouse_id}, day{" "}
          {state.snapshot.simulated_day}, {state.snapshot.entities.length} entities.
        </p>
      );
  }
}
