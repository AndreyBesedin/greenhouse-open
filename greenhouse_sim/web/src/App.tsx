import { type BuildInfo, buildInfo } from "./buildInfo";

export function App({ build = buildInfo }: { build?: BuildInfo }) {
  return (
    <main>
      <h1>greenhouse-sim viewer</h1>
      <dl>
        <dt>Simulator version</dt>
        <dd>{build.simulatorVersion}</dd>
        <dt>Built from commit</dt>
        <dd>{build.sourceCommit}</dd>
      </dl>
    </main>
  );
}
