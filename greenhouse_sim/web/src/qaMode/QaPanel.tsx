import type { ReactNode } from "react";

import type { BuildInfo } from "../buildInfo";
import { describeManifest, type RunManifestState, type ServedVersionState } from "./manifest";

/** What the run is made from, in QA mode: a scenario's run's manifest, its
 * version, seed, season and models; and the simulator and the viewer, each
 * one's version and commit, the simulator's as it says itself and the
 * viewer's as it was built, warning when the two commits differ. */
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
        ];
  const simulator =
    served.status === "loaded"
      ? `${served.served.version}, commit ${served.served.commit}`
      : served.status === "unavailable"
        ? `cannot be read: ${served.reason}`
        : "reading…";
  const commitsDiffer = served.status === "loaded" && served.served.commit !== build.sourceCommit;
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
 * QA mode's panel (P09.6), shown only in QA mode and marked as QA's: what
 * the run is made from, its manifest and the versions and commits of the
 * simulator and the viewer.
 */
export function QaPanel({
  build,
  served,
  manifest,
}: {
  build: BuildInfo;
  served: ServedVersionState;
  /** The manifest of the scenario's run drawn; none for another scene. */
  manifest: RunManifestState;
}) {
  return (
    <section className="qa-panel" aria-label="QA mode">
      <RunManifestList build={build} served={served} manifest={manifest} />
    </section>
  );
}
