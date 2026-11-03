import { useState } from "react";

import { BUILDER_PATH } from "../builder/Builder";
import { loadScenarios, SCENARIOS_URL, type ScenariosState } from "../scenarios";
import { useLoad } from "../useLoad";
import { followAddress } from "./follow";
import { newRunScenario, REPOSITORY_URL, replayAddress, runsScenario } from "./paths";
import { loadPlaying, runKey } from "./playing";
import { RunProgress, StatusChip } from "./RunParts";
import { RunsDialog } from "./RunsDialog";
import { ScenarioCombobox } from "./ScenarioCombobox";
import {
  isComputing,
  loadStoredRuns,
  runCounts,
  type StoredRun,
  type StoredRunsState,
  startedText,
} from "./storedRuns";

/** How many of the latest runs the page lists. */
const RECENT_RUNS = 5;

const NOT_PLAYING: ReadonlySet<string> = new Set();

/** Goes to an address, a page of its own. */
function goTo(address: string): void {
  location.assign(address);
}

/**
 * The page where a person decides what to do (P17.5, decision 0065): open a
 * scenario, or build one, or pick up a run where it was left. The scenarios
 * and the runs kept are the simulator's; `navigate` goes to another page.
 */
export function Landing({
  navigate = goTo,
  hash = location.hash,
}: {
  navigate?: (address: string) => void;
  /** The address's fragment, which can ask for a scenario's new-run form. */
  hash?: string;
}) {
  const scenarios = useLoad(SCENARIOS_URL, (_url, fetchFn) => loadScenarios(fetchFn));
  // The runs kept are asked for again each time one is started or removed.
  const [asked, setAsked] = useState(0);
  const runs = useLoad(asked, (_asked, fetchFn) => loadStoredRuns(fetchFn), {
    key: (each) => `runs-${each}`,
  });
  const [opened, setOpened] = useState(() => newRunScenario(hash) ?? runsScenario(hash));
  const [form, setForm] = useState(() => newRunScenario(hash) !== null);
  const chosen =
    opened !== null && scenarios.status === "loaded"
      ? scenarios.scenarios.find((each) => each.id === opened)
      : undefined;
  const counts = runs.status === "loaded" ? runCounts(runs.runs) : null;
  // A run is followed from here only if its scenario's playback is playing it.
  const computing =
    runs.status === "loaded"
      ? [...new Set(runs.runs.filter(isComputing).map((run) => run.scenario_id))].sort()
      : [];
  const playing = useLoad(computing.length === 0 ? null : computing, loadPlaying, {
    // Asked again with the runs, since a start changes which epoch plays.
    key: (ids) => `${asked}:${ids.join(",")}`,
  });
  const followed = playing.status === "loaded" ? playing.epochs : NOT_PLAYING;
  const names = new Map(
    scenarios.status === "loaded" ? scenarios.scenarios.map((s) => [s.id, s.name]) : [],
  );
  return (
    <div className="landing">
      <header className="landing-header">
        <h1>Greenhouse simulator</h1>
        <a href={REPOSITORY_URL} target="_blank" rel="noopener" className="landing-link-button">
          Contribute
        </a>
      </header>
      <main className="landing-main">
        <h2>What would you like to do?</h2>
        <p className="landing-lead">
          Open a scenario to look at it or follow a run of it, or build a new scenario.
        </p>
        <div className="landing-cards">
          <section className="landing-card landing-card-wide" aria-labelledby="landing-open">
            <h3 id="landing-open">Open a scenario</h3>
            <p>Search by name, identifier or description.</p>
            <ScenarioChoice
              scenarios={scenarios}
              counts={counts}
              onChoose={(id) => {
                setForm(false);
                setOpened(id);
              }}
              onBuild={() => navigate(BUILDER_PATH)}
            />
          </section>
          <section className="landing-card" aria-labelledby="landing-build">
            <h3 id="landing-build">Build a scenario</h3>
            <p>Lay out a house, its rows, weather and crop models, then run it.</p>
            <a href={BUILDER_PATH} className="landing-link-button landing-primary">
              Open the builder
            </a>
          </section>
        </div>
        <section aria-labelledby="landing-recent">
          <h3 id="landing-recent">Recent runs</h3>
          <RecentRuns runs={runs} names={names} followed={followed} />
        </section>
      </main>
      {chosen !== undefined && (
        <RunsDialog
          key={chosen.id}
          scenario={chosen}
          runs={
            runs.status === "loaded" ? runs.runs.filter((run) => run.scenario_id === chosen.id) : []
          }
          followed={followed}
          newRun={form}
          onClose={() => setOpened(null)}
          onChanged={() => setAsked((previous) => previous + 1)}
        />
      )}
    </div>
  );
}

function ScenarioChoice({
  scenarios,
  counts,
  onChoose,
  onBuild,
}: {
  scenarios: ScenariosState;
  counts: ReadonlyMap<string, number> | null;
  onChoose: (scenarioId: string) => void;
  onBuild: () => void;
}) {
  switch (scenarios.status) {
    case "loaded":
      return (
        <ScenarioCombobox
          scenarios={scenarios.scenarios}
          counts={counts}
          onChoose={onChoose}
          onBuild={onBuild}
        />
      );
    case "unavailable":
      return (
        <p role="alert">
          The simulator API is not reachable ({scenarios.reason}). Start it with{" "}
          <code>python -m greenhouse_sim.api</code>.
        </p>
      );
    default:
      return <p>Loading scenarios from the simulator…</p>;
  }
}

function RecentRuns({
  runs,
  names,
  followed,
}: {
  runs: StoredRunsState | { status: "none" };
  names: ReadonlyMap<string, string>;
  /** The stored epochs that their scenarios' playbacks are playing. */
  followed: ReadonlySet<string>;
}) {
  if (runs.status === "unavailable") {
    return <p role="alert">The runs kept cannot be listed: {runs.reason}.</p>;
  }
  if (runs.status !== "loaded") {
    return <p>Loading the runs kept…</p>;
  }
  if (runs.runs.length === 0) {
    return <p>No run has been kept yet. Open a scenario to start one.</p>;
  }
  return (
    <ul className="landing-runs">
      {runs.runs.slice(0, RECENT_RUNS).map((run) => (
        <RunRow
          key={runKey(run)}
          run={run}
          name={names.get(run.scenario_id)}
          following={followed.has(runKey(run))}
        />
      ))}
    </ul>
  );
}

function RunRow({
  run,
  name,
  following,
}: {
  run: StoredRun;
  name: string | undefined;
  following: boolean;
}) {
  const started = startedText(run);
  const whose = name ?? run.scenario_id;
  return (
    <li className="landing-run">
      <div className="landing-run-name">
        <strong>{whose}</strong>
        <span>
          {run.seed === null ? "the scenario's seed" : `seed ${run.seed}`} · epoch {run.epoch}
          {started === "" ? "" : ` · ${started}`}
        </span>
      </div>
      <StatusChip run={run} />
      <RunProgress run={run} name={`the run of ${whose}`} />
      <a href={replayAddress(run.run_id, run.epoch)} className="landing-link-button">
        Replay
      </a>
      {following && (
        <a href={followAddress(run.scenario_id, run.layout)} className="landing-link-button">
          Follow
        </a>
      )}
    </li>
  );
}
