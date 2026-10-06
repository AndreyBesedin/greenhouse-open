import { DEFAULT_LAYOUT, type ScenariosState } from "./scenarios";

/** The simulator's scenarios, each to be shown, with any of its layouts, or
 * played live. */
export function ScenarioList({
  state,
  shownLayout = null,
  onShow,
  onLive,
}: {
  state: ScenariosState;
  /** The scenario on show and its layout, which its layout picker shows. */
  shownLayout?: { scenarioId: string; layout: string } | null;
  onShow?: (scenarioId: string, layout?: string) => void;
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
    case "loaded": {
      const choosing = onShow && state.scenarios.some((scenario) => scenario.layouts.length > 1);
      return (
        <table>
          <caption>Scenarios</caption>
          <thead>
            <tr>
              <th>Scenario</th>
              <th>Name</th>
              <th>Plants</th>
              <th>Days</th>
              {choosing && <th>Layout</th>}
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
                {choosing && (
                  <td>
                    {scenario.layouts.length > 1 && (
                      <select
                        aria-label={`Layout of ${scenario.id}`}
                        value={
                          shownLayout?.scenarioId === scenario.id
                            ? shownLayout.layout
                            : DEFAULT_LAYOUT
                        }
                        onChange={(event) => onShow(scenario.id, event.target.value)}
                      >
                        {scenario.layouts.map((layout) => (
                          <option key={layout} value={layout}>
                            {layout}
                          </option>
                        ))}
                      </select>
                    )}
                  </td>
                )}
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
}
