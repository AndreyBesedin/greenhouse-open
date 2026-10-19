import { DEFAULT_LAYOUT, type ScenarioSummary, type ScenariosState } from "./scenarios";

/** Whether a scenario's name, identifier or description holds `filter`,
 * whatever their case; every one does an empty filter. */
export function scenarioMatches(scenario: ScenarioSummary, filter: string): boolean {
  const wanted = filter.trim().toLowerCase();
  return [scenario.name, scenario.id, scenario.description].some((text) =>
    text.toLowerCase().includes(wanted),
  );
}

/** The simulator's scenarios, each to be opened, with any of its layouts,
 * or played live; those `filter` matches (`scenarioMatches`). */
export function ScenarioList({
  state,
  shownLayout = null,
  filter = "",
  onShow,
  onLive,
  onFollow,
}: {
  state: ScenariosState;
  /** The scenario on show and its layout, which its layout picker shows. */
  shownLayout?: { scenarioId: string; layout: string } | null;
  filter?: string;
  onShow?: (scenarioId: string, layout?: string) => void;
  onLive?: (scenarioId: string) => void;
  /** Follows its own run as it is played back (decision 0041). */
  onFollow?: (scenarioId: string) => void;
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
      const listed = state.scenarios.filter((scenario) => scenarioMatches(scenario, filter));
      if (listed.length === 0) {
        return <p>No scenario matches “{filter.trim()}”.</p>;
      }
      return (
        <table>
          <caption>Scenarios</caption>
          <thead>
            <tr>
              <th>Scenario</th>
              <th>Plants</th>
              <th>Days</th>
              {choosing && <th>Layout</th>}
              {onShow && <th />}
              {onLive && <th />}
              {onFollow && <th />}
            </tr>
          </thead>
          <tbody>
            {listed.map((scenario) => (
              <tr key={scenario.id}>
                {/* By name, and under it its description, cut to a line until
                    the row is hovered or focused; its identifier, which
                    addresses use, on hover too. */}
                <td title={`${scenario.id}: ${scenario.description}`}>
                  <span className="scenario-name">{scenario.name}</span>
                  <span className="scenario-description">{scenario.description}</span>
                </td>
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
                      aria-label={`Open ${scenario.id}`}
                      onClick={() => onShow(scenario.id)}
                    >
                      Open
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
                {onFollow && (
                  <td>
                    <button
                      type="button"
                      aria-label={`Follow ${scenario.id}`}
                      title="Follow its own run as it is played back, as a consumer reads it"
                      onClick={() => onFollow(scenario.id)}
                    >
                      Follow
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
