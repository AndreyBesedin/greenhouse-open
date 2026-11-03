import { useId } from "react";

import type { PositionState } from "./position";
import { ReplayTimeline } from "./ReplayTimeline";
import { computedText, dayAway, dayLabel, type Span } from "./timeline";

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
  return { startS: 0, frontierS: position.frontier_s, endS: position.duration_s };
}

/** Whether a run can be followed at its frontier: only while it is still
 * being computed. A finished or interrupted one has no newest day to wait
 * for. */
export function canFollow(position: PositionState): boolean {
  return position.status === "queued" || position.status === "running";
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
  onPlay,
  onPause,
  onFollow,
  onSeek,
  onPace,
}: {
  position: PositionState;
  /** Why the latest move did nothing, if it was refused. */
  refused?: string | null;
  onPlay: () => void;
  onPause: () => void;
  onFollow: () => void;
  onSeek: (timeS: number) => void;
  onPace: (secondsPerDay: number) => void;
}) {
  const span = spanOf(position);
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
      <div className="replay-controls">
        <div className="replay-buttons">
          <button
            type="button"
            className="replay-button"
            aria-label="Previous day"
            onClick={() => onSeek(dayAway(position.time_s, -1, span))}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M19 6l-8 6 8 6zM7 6v12h-2V6z" />
            </svg>
          </button>
          <button
            type="button"
            className="replay-button replay-play"
            aria-label={position.playing ? "Pause" : "Play"}
            onClick={position.playing ? onPause : onPlay}
          >
            {position.playing ? (
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="currentColor"
                aria-hidden="true"
              >
                <path d="M6 5h4v14H6zM14 5h4v14h-4z" />
              </svg>
            ) : (
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="currentColor"
                aria-hidden="true"
              >
                <path d="M7 4l13 8-13 8z" />
              </svg>
            )}
          </button>
          <button
            type="button"
            className="replay-button"
            aria-label="Next day"
            onClick={() => onSeek(dayAway(position.time_s, 1, span))}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M5 6l8 6-8 6zM17 6v12h2V6z" />
            </svg>
          </button>
        </div>
        <strong className="replay-moment" data-testid="replay-moment">
          {dayLabel(position.time_s)}
        </strong>
        <span className="replay-computed-text" data-testid="replay-computed">
          {computedText(span)}
        </span>
        <span className="replay-spacer" />
        <label className="replay-pace" htmlFor={paceId}>
          Pace
          <select
            id={paceId}
            value={position.seconds_per_day}
            onChange={(event) => onPace(Number(event.currentTarget.value))}
          >
            {paces.map((seconds) => (
              <option key={seconds} value={seconds}>
                {seconds} s a day
              </option>
            ))}
          </select>
        </label>
        {canFollow(position) && (
          <button
            type="button"
            className="replay-follow"
            aria-pressed={position.following}
            // A position that follows is held where it is by pausing it, which
            // clears the following and the playing alike (it shows Play then).
            onClick={position.following ? onPause : onFollow}
          >
            Follow the newest day
          </button>
        )}
      </div>
      <ReplayTimeline span={span} timeS={position.time_s} onSeek={onSeek} />
    </section>
  );
}
