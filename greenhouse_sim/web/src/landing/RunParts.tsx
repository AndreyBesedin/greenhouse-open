import { progressShare, progressText, STATUS_LABEL, type StoredRun } from "./storedRuns";

/** A run's status, in words: never a colour alone. */
export function StatusChip({ run }: { run: StoredRun }) {
  return (
    <span className={`landing-status landing-status-${run.status}`}>
      {STATUS_LABEL[run.status]}
    </span>
  );
}

/** How far a run is computed: a bar, and the days in words. `name` says
 * whose, for whoever hears the bar. */
export function RunProgress({ run, name }: { run: StoredRun; name: string }) {
  return (
    <div className="landing-run-progress">
      <progress max={1} value={progressShare(run)} aria-label={`Progress of ${name}`} />
      <span>{progressText(run)}</span>
    </div>
  );
}
