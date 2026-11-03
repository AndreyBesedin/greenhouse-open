import { type KeyboardEvent, type PointerEvent, useRef } from "react";

import { DAY_S } from "../clock";
import {
  computedShare,
  dayLabel,
  dayTicks,
  fractionOf,
  momentAt,
  movedByKey,
  type Span,
} from "./timeline";

const PERCENT = 100;

/**
 * A timeline over the whole of a stored epoch (P17.6, decision 0065): what is
 * computed is filled, what is not yet is hatched, the frontier is marked, and
 * the handle moves anywhere in what is computed, by the pointer or the keys.
 * A moment past the frontier cannot be asked for: a position is a place over
 * what is committed.
 */
export function ReplayTimeline({
  span,
  timeS,
  onSeek,
}: {
  span: Span;
  timeS: number;
  onSeek: (timeS: number) => void;
}) {
  const track = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  function seekAt(event: PointerEvent): void {
    const box = track.current?.getBoundingClientRect();
    if (box === undefined || box.width <= 0) {
      return;
    }
    onSeek(momentAt((event.clientX - box.left) / box.width, span));
  }

  function onKey(event: KeyboardEvent): void {
    const moved = movedByKey(event.key, timeS, span);
    if (moved !== null) {
      event.preventDefault();
      onSeek(moved);
    }
  }

  const computed = computedShare(span) * PERCENT;
  const at = fractionOf(timeS, span) * PERCENT;
  return (
    <div className="replay-timeline">
      <div
        ref={track}
        className="replay-track"
        data-testid="replay-track"
        onPointerDown={(event) => {
          dragging.current = true;
          event.currentTarget.setPointerCapture?.(event.pointerId);
          seekAt(event);
        }}
        onPointerMove={(event) => {
          if (dragging.current) {
            seekAt(event);
          }
        }}
        onPointerUp={() => {
          dragging.current = false;
        }}
        onPointerCancel={() => {
          dragging.current = false;
        }}
      >
        <div className="replay-computed" style={{ width: `${computed}%` }} />
        <div className="replay-frontier" style={{ left: `${computed}%` }} />
        <div
          className="replay-handle"
          role="slider"
          tabIndex={0}
          aria-label="Position in the run"
          aria-orientation="horizontal"
          aria-valuemin={span.startS}
          aria-valuemax={span.frontierS}
          aria-valuenow={timeS}
          aria-valuetext={dayLabel(timeS)}
          data-testid="replay-handle"
          style={{ left: `${at}%` }}
          onKeyDown={onKey}
        />
      </div>
      <div className="replay-ticks" aria-hidden="true">
        {dayTicks(span).map((day) => (
          <span
            key={day}
            className="replay-tick"
            style={{ left: `${fractionOf(day * DAY_S, span) * PERCENT}%` }}
          >
            {day === 0 ? "start" : day}
          </span>
        ))}
      </div>
      <ul className="replay-legend">
        <li>
          <span className="replay-swatch replay-swatch-computed" aria-hidden="true" />
          computed, can be played
        </li>
        <li>
          <span className="replay-swatch replay-swatch-pending" aria-hidden="true" />
          not computed yet
        </li>
      </ul>
    </div>
  );
}
