import { useId } from "react";

import { Button } from "../design/Button";
import { IconButton } from "../design/IconButton";
import { PauseIcon, PlayIcon, StepBackIcon, StepForwardIcon } from "../icons";
import type { PositionState } from "./position";
import { ReplayTimeline } from "./ReplayTimeline";
import { computedText, dayAway, dayLabel, type Span } from "./timeline";

// Play and Pause, the transport's main button, drawn a little larger than a day's steps.
const PLAY_ICON_PX = 20;

const QUICK_S = 2;
const BRISK_S = 5;
const STEADY_S = 10;
const LEISURELY_S = 30;
const SLOW_S = 60;
/** How fast a day plays, in real seconds, to choose from: from a quick two
 * seconds to a slow minute. */
export const PACES_S: readonly number[] = [QUICK_S, BRISK_S, STEADY_S, LEISURELY_S, SLOW_S];

/** The part of a run a position can be at: from its start, which is the
 * run's own, to the frontier. */
export function spanOf(position: PositionState): Span {
  return { startS: position.start_s, frontierS: position.frontier_s, endS: position.duration_s };
}

/** Whether a run can be followed at its frontier: only while it is still
 * being computed. A finished or interrupted one has no newest day to wait
 * for. */
export function canFollow(position: PositionState): boolean {
  return position.status === "queued" || position.status === "running";
}

/** What is said while a fork's replay is held back by the fork's frontier, or
 * null. A fork's position is bound for the moment it was made from, and stands
 * at the newest moment computed until the fork is computed that far; then it
 * stands there, by itself (decision 0065). One moved back, or a fork that is no
 * longer computed, waits for nothing. Moved to the frontier, as by End, it reads
 * as waiting until the frontier passes the fork's moment. */
export function forkWaitNote(position: PositionState): string | null {
  const fork = position.fork;
  if (
    fork === null ||
    !canFollow(position) ||
    position.frontier_s >= fork.at_s ||
    position.time_s < position.frontier_s
  ) {
    return null;
  }
  return `This fork was made at ${dayLabel(fork.at_s)}: until it is computed that far, the newest moment computed is shown, and the replay moves on to ${dayLabel(fork.at_s)} by itself.`;
}

/**
 * What moves a position, under the scene (P17.6): a day back, play, a day
 * on, where it stands and how far the epoch is computed, how fast a day
 * plays, and whether to stay at the newest day; and the timeline over the
 * whole run.
 */
export function ReplayTransport({
  position,
  refused = null,
  heading = null,
  onPlay,
  onPause,
  onFollow,
  onSeek,
  onPace,
}: {
  position: PositionState;
  /** Why the latest move did nothing, if it was refused. */
  refused?: string | null;
  /** The moment last sought, while its answer is on its way: the handle stands
   * there and the moves go from there, while the words say where the position is. */
  heading?: number | null;
  onPlay: () => void;
  onPause: () => void;
  onFollow: () => void;
  onSeek: (timeS: number) => void;
  onPace: (secondsPerDay: number) => void;
}) {
  const span = spanOf(position);
  const from = heading ?? position.time_s;
  // At the frontier of a run interrupted or failed, nothing comes for it to play over.
  const nothingToCome =
    (position.status === "interrupted" || position.status === "failed") &&
    position.time_s >= position.frontier_s;
  const atItsEnd = position.duration_s !== null && position.time_s >= position.duration_s;
  const forkWait = forkWaitNote(position);
  const paceId = useId();
  const paces = PACES_S.includes(position.seconds_per_day)
    ? PACES_S
    : [...PACES_S, position.seconds_per_day].sort((a, b) => a - b);
  return (
    <section className="replay-transport" aria-label="Move through the run">
      {refused !== null && (
        <p role="alert" className="replay-refused">
          That did not reach the run: {refused}. Reload the page to open it again.
        </p>
      )}
      {forkWait !== null && (
        <p role="status" className="replay-refused" data-testid="replay-fork-wait">
          {forkWait}
        </p>
      )}
      <div className="replay-controls">
        <div className="replay-buttons">
          <IconButton label="Previous day" onClick={() => onSeek(dayAway(from, -1, span))}>
            <StepBackIcon />
          </IconButton>
          <IconButton
            tone="primary"
            className="replay-play"
            label={position.playing ? "Pause" : "Play"}
            // At the run's end there is nothing to play: it would stop at once. One
            // already waiting at a frontier with nothing to come can still be told
            // to stop waiting.
            disabled={atItsEnd || (nothingToCome && !position.playing)}
            onClick={position.playing ? onPause : onPlay}
          >
            {position.playing ? (
              <PauseIcon size={PLAY_ICON_PX} />
            ) : (
              <PlayIcon size={PLAY_ICON_PX} />
            )}
          </IconButton>
          <IconButton label="Next day" onClick={() => onSeek(dayAway(from, 1, span))}>
            <StepForwardIcon />
          </IconButton>
        </div>
        <strong className="replay-moment" data-testid="replay-moment">
          {dayLabel(position.time_s)}
        </strong>
        <span className="replay-computed-text" data-testid="replay-computed">
          {computedText(span)}
        </span>
        <span className="replay-spacer" />
        {/* How fast the replay shows the run, which is not how fast the run is
            computed: the form that starts a run asks that (P22.5). */}
        <label className="replay-pace" htmlFor={paceId}>
          Shows a day in
          <select
            id={paceId}
            value={position.seconds_per_day}
            onChange={(event) => onPace(Number(event.currentTarget.value))}
          >
            {paces.map((seconds) => (
              <option key={seconds} value={seconds}>
                {seconds} s
              </option>
            ))}
          </select>
        </label>
        {canFollow(position) && (
          <Button
            className="replay-follow"
            aria-pressed={position.following}
            // A position that follows is held where it is by pausing it, which
            // clears the following and the playing alike (it shows Play then).
            onClick={position.following ? onPause : onFollow}
          >
            Follow the newest day
          </Button>
        )}
      </div>
      <ReplayTimeline span={span} timeS={from} onSeek={onSeek} />
    </section>
  );
}
