import type { ScenariosState } from "./scenarios";

export function ScenarioList({
  state,
  onShow,
  onLive,
}: {
  state: ScenariosState;
  onShow?: (scenarioId: string) => void;
  onLive?: (scenarioId: string) => void;
}) {
  switch (state.status) {
    case "loading":
      return <p>Loading scenarios from the simulator…</p>;
    case "unavailable":
      return (
        <p role="alert">
          The simulator API is not reachable ({state.reason}). Start it with{" "}
          <code>python -m greenhouse_sim.api</code>.
        </p>
      );
    case "loaded":
      return (
        <table>
          <caption>Scenarios</caption>
          <thead>
            <tr>
              <th>Scenario</th>
              <th>Name</th>
              <th>Plants</th>
              <th>Days</th>
              {onShow && <th />}
              {onLive && <th />}
            </tr>
          </thead>
          <tbody>
            {state.scenarios.map((scenario) => (
              <tr key={scenario.id}>
                <td>
                  <code>{scenario.id}</code>
                </td>
                <td title={scenario.description}>{scenario.name}</td>
                <td>{scenario.plants}</td>
                <td>{scenario.duration_days}</td>
                {onShow && (
                  <td>
                    <button
                      type="button"
                      aria-label={`Show ${scenario.id}`}
                      onClick={() => onShow(scenario.id)}
                    >
                      Show
                    </button>
                  </td>
                )}
                {onLive && (
                  <td>
                    <button
                      type="button"
                      aria-label={`Play ${scenario.id} live`}
                      onClick={() => onLive(scenario.id)}
                    >
                      Live
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      );
  }
}
