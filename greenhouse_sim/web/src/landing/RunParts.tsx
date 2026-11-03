import { followAddress } from "./follow";
import { replayAddress } from "./paths";
import { runKey } from "./playing";
import {
  isComputing,
  progressShare,
  progressText,
  STATUS_LABEL,
  type StoredRun,
} from "./storedRuns";

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

/** Where a run is followed, if it can be: in the viewer if a playback plays it
 * (`loadPlaying`), else in its replay, at the newest day, while it is computed. */
export function followHref(run: StoredRun, played: ReadonlySet<string>): string | null {
  if (played.has(runKey(run))) {
    return followAddress(run.scenario_id, run.layout);
  }
  return isComputing(run) ? replayAddress(run.run_id, run.epoch, true) : null;
}

/** A link to follow a run, if it can be followed. */
export function FollowLink({ run, played }: { run: StoredRun; played: ReadonlySet<string> }) {
  const href = followHref(run, played);
  return (
    href !== null && (
      <a href={href} className="landing-link-button">
        Follow
      </a>
    )
  );
}
