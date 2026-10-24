import type { ReactNode } from "react";

import type { BuildInfo } from "../buildInfo";
import {
  describeManifest,
  type RunManifestState,
  type ServedVersionState,
  UNKNOWN_COMMIT,
} from "./manifest";
import { describeRunState, type RunStateState } from "./state";

/** A sensor's or a camera's line, a button that selects it where the panel
 * can: in a dense crop it is easier to find here than to click in the view. */
function Selectable({
  id,
  text,
  onSelect,
}: {
  id: string;
  text: string;
  onSelect: ((id: string) => void) | null;
}) {
  return onSelect === null ? (
    text
  ) : (
    <button type="button" className="select-link" onClick={() => onSelect(id)}>
      {text}
    </button>
  );
}

/** What each process of the scenario's run drawn holds at its moment, as
 * the simulator says: the clock, the house's air, the crop, the levels and
 * the latest commands, each sensor's freshness, a stale one marked, and
 * each camera's frames; each sensor and camera selects it, if `onSelect`. */
function DeveloperList({
  state,
  onSelect,
}: {
  state: RunStateState;
  onSelect: ((id: string) => void) | null;
}) {
  if (state.status === "none") {
    return null;
  }
  const described = state.status === "loaded" ? describeRunState(state.state) : null;
  return (
    <details className="developer" open>
      <summary>Developer</summary>
      {state.status === "loading" && <p>Reading what the run holds…</p>}
      {state.status === "unavailable" && <p>What the run holds cannot be read: {state.reason}.</p>}
      {described !== null && state.status === "loaded" && (
        <dl>
          <Row title="Clock" testId="developer-clock">
            {described.clock}
          </Row>
          <Row title="House air" testId="developer-house-air">
            {described.houseAir}
          </Row>
          <Row title="Crop" testId="developer-crop">
            {described.crop}
          </Row>
          <Row title="Levels" testId="developer-levels">
            {described.levels}
          </Row>
          <Row title="Commands" testId="developer-commands">
            {`${state.state.commandsGiven} given${described.commands.length > 0 ? ", the latest:" : ""}`}
            {described.commands.length > 0 && (
              <ol data-testid="developer-latest-commands">
                {described.commands.map((command, index) => (
                  // biome-ignore lint/suspicious/noArrayIndexKey: two commands may be alike.
                  <li key={index}>{command}</li>
                ))}
              </ol>
            )}
          </Row>
          <Row title="Sensors" testId="developer-sensors">
            <ul>
              {described.sensors.map((sensor) => (
                <li key={sensor.id} className={sensor.stale ? "stale" : undefined}>
                  <Selectable id={sensor.id} text={sensor.text} onSelect={onSelect} />
                </li>
              ))}
            </ul>
          </Row>
          <Row title="Cameras" testId="developer-cameras">
            {described.cameras.length === 0 ? (
              "none"
            ) : (
              <ul>
                {described.cameras.map((camera) => (
                  <li key={camera.id}>
                    <Selectable id={camera.id} text={camera.text} onSelect={onSelect} />
                  </li>
                ))}
              </ul>
            )}
          </Row>
        </dl>
      )}
    </details>
  );
}

/** What the run is made from, in QA mode: a scenario's run's manifest, its
 * version, seed, season and models; and the simulator and the viewer, each
 * one's version and commit, the simulator's as it says itself and the
 * viewer's as it was built, warning when the two commits are known and
 * differ. A simulator installed as a package, rather than run from a git
 * checkout, does not know its commit. */
function RunManifestList({
  build,
  served,
  manifest,
}: {
  build: BuildInfo;
  served: ServedVersionState;
  manifest: RunManifestState;
}) {
  const described = manifest.status === "loaded" ? describeManifest(manifest.manifest) : null;
  const rows: [string, string, string][] =
    described === null
      ? []
      : [
          ["Scenario", "manifest-scenario", described.scenario],
          ["Seed", "manifest-seed", described.seed],
          ["Season", "manifest-season", described.season],
          ["Crop", "manifest-crop", described.crop],
          ["Airflow", "manifest-airflow", described.airflow],
          ["Weather", "manifest-weather", described.weather],
          ["Models", "manifest-models", described.models],
        ];
  const simulator =
    served.status === "loaded"
      ? `${served.served.version}, commit ${served.served.commit}`
      : served.status === "unavailable"
        ? `cannot be read: ${served.reason}`
        : "reading…";
  const commitsDiffer =
    served.status === "loaded" &&
    served.served.commit !== UNKNOWN_COMMIT &&
    build.sourceCommit !== UNKNOWN_COMMIT &&
    served.served.commit !== build.sourceCommit;
  return (
    <details className="run-manifest" open>
      <summary>Run manifest</summary>
      {manifest.status === "loading" && <p>Reading the run's manifest…</p>}
      {manifest.status === "unavailable" && (
        <p>The run's manifest cannot be read: {manifest.reason}.</p>
      )}
      <dl>
        {rows.map(([title, testId, text]) => (
          <Row key={testId} title={title} testId={testId}>
            {text}
          </Row>
        ))}
        <Row title="Simulator" testId="manifest-simulator">
          {simulator}
        </Row>
        <Row title="Viewer" testId="manifest-viewer">
          {`${build.simulatorVersion}, commit ${build.sourceCommit}`}
        </Row>
      </dl>
      {commitsDiffer && (
        <p className="stale" data-testid="manifest-commits-differ">
          The viewer was built from another commit than the simulator runs.
        </p>
      )}
    </details>
  );
}

function Row({ title, testId, children }: { title: string; testId: string; children: ReactNode }) {
  return (
    <>
      <dt>{title}</dt>
      <dd data-testid={testId}>{children}</dd>
    </>
  );
}

/**
 * QA mode's panel (P09.6), shown only in QA mode and marked as QA's: the
 * developer's list of what each process of the run holds at its moment,
 * and what the run is made from, its manifest and the versions and commits
 * of the simulator and the viewer.
 */
export function QaPanel({
  build,
  served,
  manifest,
  state,
  onSelect = null,
}: {
  build: BuildInfo;
  served: ServedVersionState;
  /** The manifest of the scenario's run drawn, and what each of its
   * processes holds at its moment; none for another scene. */
  manifest: RunManifestState;
  state: RunStateState;
  /** Selects a sensor or a camera, by its identifier in the run. */
  onSelect?: ((id: string) => void) | null;
}) {
  return (
    <section className="qa-panel" aria-label="QA mode">
      <DeveloperList state={state} onSelect={onSelect} />
      <RunManifestList build={build} served={served} manifest={manifest} />
    </section>
  );
}
