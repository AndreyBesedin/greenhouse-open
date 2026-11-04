import { replayAddress } from "./paths";
import {
  isComputing,
  progressShare,
  progressText,
  STATUS_LABEL,
  type StoredRun,
} from "./storedRuns";

/** What is said of a run with files missing, beside the status it has. */
export const DAMAGED_NOTE = "Files of this run are missing, so it cannot be read whole.";

/** What is said of a run asked to stop, whose worker has not yet looked. */
export const STOPPING_NOTE =
  "Its worker stops at its next look, with what it has committed. The run then reads Interrupted, and can be resumed or deleted.";

/** A run's status, in words: never a colour alone. One with files missing is
 * called so whatever else it is, since its status says it is whole. */
export function StatusChip({ run }: { run: StoredRun }) {
  if (run.damaged) {
    return (
      <span className="landing-status landing-status-failed" title={DAMAGED_NOTE}>
        Damaged
        <span className="visually-hidden"> {DAMAGED_NOTE}</span>
      </span>
    );
  }
  if (run.stopping) {
    return (
      <span className={`landing-status landing-status-${run.status}`} title={STOPPING_NOTE}>
        Stopping
        <span className="visually-hidden"> {STOPPING_NOTE}</span>
      </span>
    );
  }
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

/** A link to a run's replay, unless it has files missing. `label` names the run
 * for whoever hears the link, if the list does not. */
export function ReplayLink({ run, label }: { run: StoredRun; label?: string }) {
  return (
    !run.damaged && (
      <a
        href={replayAddress(run.run_id, run.epoch)}
        className="landing-link-button landing-run-action landing-run-replay"
        aria-label={label}
      >
        Replay
      </a>
    )
  );
}

/** A link to a run's replay at the newest day, while it is computed: one with
 * files missing has nothing whole to show. */
export function FollowLink({ run }: { run: StoredRun }) {
  return (
    isComputing(run) &&
    !run.damaged && (
      <a
        href={replayAddress(run.run_id, run.epoch, true)}
        className="landing-link-button landing-run-action landing-run-follow"
      >
        Follow
      </a>
    )
  );
}
