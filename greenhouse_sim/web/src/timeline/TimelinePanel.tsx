import { useState } from "react";

import type { RunParts } from "../scene/run";
import { useLoad } from "../useLoad";
import {
  describeTurn,
  eventsAt,
  loadTimeline,
  type Timeline,
  type TimelineEvent,
  timelineUrl,
  timelineWindow,
  ZOOMS,
} from "./timeline";

// Each lane's strip, in its own units, and its ticks to half a unit, so that
// a day's thousands of events are a few hundred strokes.
const WIDTH = 240;
const HEIGHT = 10;
const TICKS_PER_UNIT = 2;
// The zoom it opens at: an hour.
const FIRST_ZOOM_S = 3600;

/** A process's events in a window as ticks across it, each tick once. */
function ticks(timeline: Timeline, process: number): { path: string; count: number } {
  const span = timeline.untilS - timeline.fromS;
  const columns = new Set<number>();
  let count = 0;
  for (const [at, timeS] of timeline.timesS.entries()) {
    if (timeline.process[at] === process) {
      count += 1;
      columns.add(Math.round(((timeS - timeline.fromS) / span) * WIDTH * TICKS_PER_UNIT));
    }
  }
  const path = [...columns].map((column) => `M${column / TICKS_PER_UNIT} 0V${HEIGHT}`).join("");
  return { path, count };
}

/** Each process's events at a moment, in the order the processes take their
 * turns. */
function turns(timeline: Timeline, seconds: number): [string, TimelineEvent[]][] {
  const byProcess = new Map<string, TimelineEvent[]>();
  for (const event of eventsAt(timeline, seconds)) {
    byProcess.set(event.process, [...(byProcess.get(event.process) ?? []), event]);
  }
  return [...byProcess];
}

/**
 * A run's timeline (P09.2), opened on demand: a lane per process, its events
 * as ticks across the window the moment drawn lies in, from a day to a
 * minute wide, with the moment marked; and what each process does at that
 * moment, in the order they take their turns.
 */
export function TimelinePanel({
  scenarioId,
  run,
  time,
}: {
  scenarioId: string;
  /** The run, asked for as its climate is. */
  run: RunParts;
  /** The moment drawn, in seconds into the run. */
  time: number;
}) {
  const [open, setOpen] = useState(false);
  const [zoom, setZoom] = useState(FIRST_ZOOM_S);
  const window = timelineWindow(time, zoom);
  const state = useLoad(open ? timelineUrl(scenarioId, run, window) : null, loadTimeline);
  return (
    <details
      className="timeline"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>Timeline</summary>
      <select
        aria-label="Timeline zoom"
        value={zoom}
        onChange={(event) => setZoom(Number(event.target.value))}
      >
        {ZOOMS.map(({ spanS, label }) => (
          <option key={spanS} value={spanS}>
            {label}
          </option>
        ))}
      </select>
      {state.status === "loading" && <p>Listing the run's events…</p>}
      {state.status === "unavailable" && <p>The run's timeline cannot be read: {state.reason}.</p>}
      {state.status === "loaded" && <TimelineLanes timeline={state.timeline} time={time} />}
    </details>
  );
}

/** A timeline's lanes, and what each process does at the moment drawn. */
export function TimelineLanes({ timeline, time }: { timeline: Timeline; time: number }) {
  const cursor = ((time - timeline.fromS) / (timeline.untilS - timeline.fromS)) * WIDTH;
  const now = turns(timeline, time);
  return (
    <figure className="timeline-lanes" aria-label="Timeline lanes">
      {timeline.processes.map((process, index) => {
        const { path, count } = ticks(timeline, index);
        return (
          <div className="timeline-lane" key={process}>
            <span data-testid={`timeline-${process}`}>{`${process}, ${count}`}</span>
            <svg
              viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
              preserveAspectRatio="none"
              role="img"
              aria-label={`${process}: ${count} events`}
            >
              <path className="timeline-ticks" d={path} />
              <line className="timeline-now" x1={cursor} x2={cursor} y1={0} y2={HEIGHT} />
            </svg>
          </div>
        );
      })}
      {now.length > 0 && (
        <ol className="timeline-turns" aria-label="At the moment drawn">
          {now.map(([process, events]) => (
            <li key={process} data-testid="timeline-turn">
              {process}: {describeTurn(events)}
            </li>
          ))}
        </ol>
      )}
    </figure>
  );
}
