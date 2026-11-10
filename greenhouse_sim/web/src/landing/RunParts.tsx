import { LinkButton } from "../design/LinkButton";
import { StatusChip, type StatusTone } from "../design/StatusChip";
import { failedText, NO_REASON_KEPT } from "../replay/failure";
import { replayAddress } from "./paths";
import {
  isComputing,
  progressShare,
  progressText,
  STATUS_LABEL,
  type Status,
  type StoredRun,
} from "./storedRuns";
import { NOT_MEASURED_NOTE, usageFigures } from "./usage";

/** What is said of a run with files missing, beside the status it has. */
export const DAMAGED_NOTE = "Files of this run are missing, so it cannot be read whole.";

/** What is said of a run asked to stop, whose worker has not yet looked. */
export const STOPPING_NOTE =
  "Its worker stops at its next look, with what it has committed. The run then reads Interrupted, and can be resumed or deleted.";

/** The tone a run's status is drawn in: under way or waiting, or stopped short. */
export const STATUS_TONE: Record<Status, StatusTone> = {
  queued: "active",
  running: "active",
  finished: "plain",
  failed: "problem",
  interrupted: "problem",
};

/** A run's status, in words: never a colour alone. One with files missing is
 * called so whatever else it is, since its status says it is whole. */
export function RunStatus({ run }: { run: StoredRun }) {
  const status = run.damaged ? "failed" : run.status;
  const [words, note] = run.damaged
    ? ["Damaged", DAMAGED_NOTE]
    : run.stopping
      ? ["Stopping", STOPPING_NOTE]
      : [STATUS_LABEL[run.status], undefined];
  return (
    <StatusChip tone={STATUS_TONE[status]} note={note} className="landing-run-status">
      {words}
    </StatusChip>
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

/** What is said of the replay of a run still computed, on its link. */
export const FOLLOWS_NOTE =
  "Opens at the newest day computed, and stays at it as the run computes. Play from an earlier day moves on as days arrive.";

/** The one way to watch a run: its replay (P22.2), unless it has files missing.
 * A run still computed opens following its newest day, and one computed no
 * longer at its start. `label` names the run for whoever hears the link, if
 * the list does not. */
export function ReplayLink({ run, label }: { run: StoredRun; label?: string }) {
  const computing = isComputing(run);
  return (
    !run.damaged && (
      <LinkButton
        href={replayAddress(run.run_id, run.epoch, computing)}
        className="landing-run-action landing-run-replay"
        aria-label={label}
        title={computing ? FOLLOWS_NOTE : undefined}
      >
        Replay
      </LinkButton>
    )
  );
}

/** What a run has used, figure by figure (decision 0067), on a line of its own
 * under its row: a figure no worker measured says so, and not zero. */
export function RunUsage({ run }: { run: StoredRun }) {
  return (
    <dl className="landing-run-usage">
      {usageFigures(run).map(({ label, value, measured }) => (
        <div key={label} title={measured ? undefined : NOT_MEASURED_NOTE}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Why a run failed, in the simulator's words, under its row; nothing for one
 * that did not. One ended by a limit says which, and that it can be resumed once
 * that limit is raised. */
export function RunFailure({ run }: { run: StoredRun }) {
  return (
    run.status === "failed" && (
      <p className="landing-run-reason">{failedText(run.reason ?? NO_REASON_KEPT)}</p>
    )
  );
}
