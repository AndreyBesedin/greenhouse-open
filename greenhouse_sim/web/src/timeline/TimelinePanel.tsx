import { useState } from "react";
import { CHART_WIDTH } from "../charts/chart";
import { describeTime } from "../fields/ClimateTime";
import type { RunParts } from "../scene/run";
import { useLoad } from "../useLoad";
import { loadPlanLane, type PlanEntry, type PlanLaneRun, RAN } from "./planLane";
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
      columns.add(Math.round(((timeS - timeline.fromS) / span) * CHART_WIDTH * TICKS_PER_UNIT));
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

/** A followed run's plan lane, asked for at a moment: again as the moment
 * moves on, as its clock does, and once the viewer has given it a plan. */
interface PlanRequest {
  run: PlanLaneRun;
  time: number;
}

const loadPlan = (request: PlanRequest, fetchFn: typeof fetch) =>
  loadPlanLane(request.run, fetchFn);
const planKey = ({ run, time }: PlanRequest) =>
  `${run.runId}:${run.epoch}:${run.version ?? 0}:${time}`;

/**
 * A run's timeline (P09.2), opened on demand: a lane per process, its events
 * as ticks across the window the moment drawn lies in, from a day to a
 * minute wide, with the moment marked; and what each process does at that
 * moment, in the order they take their turns. A run followed as it plays
 * has a plan lane too (P13.8): what its plans had due in the window, what
 * became of each and why, and what is still to come.
 */
export function TimelinePanel({
  scenarioId,
  run,
  time,
  played = null,
}: {
  scenarioId: string;
  /** The run, asked for as its climate is. */
  run: RunParts;
  /** The moment drawn, in seconds into the run. */
  time: number;
  /** The run followed as it plays, whose plan lane is drawn, if one is. */
  played?: PlanLaneRun | null;
}) {
  const [open, setOpen] = useState(false);
  const [zoom, setZoom] = useState(FIRST_ZOOM_S);
  const window = timelineWindow(time, zoom);
  const state = useLoad(open ? timelineUrl(scenarioId, run, window) : null, loadTimeline);
  const plan = useLoad(open && played !== null ? { run: played, time } : null, loadPlan, {
    key: planKey,
  });
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
      {state.status === "loaded" && (
        <TimelineLanes
          timeline={state.timeline}
          time={time}
          plan={plan.status === "loaded" ? plan.entries : null}
        />
      )}
      {plan.status === "unavailable" && <p>The run's plan cannot be read: {plan.reason}.</p>}
    </details>
  );
}

/** A timeline's lanes, and what each process does at the moment drawn; and
 * a followed run's plan lane, if `plan` is given. */
export function TimelineLanes({
  timeline,
  time,
  plan = null,
}: {
  timeline: Timeline;
  time: number;
  plan?: readonly PlanEntry[] | null;
}) {
  const cursor = ((time - timeline.fromS) / (timeline.untilS - timeline.fromS)) * CHART_WIDTH;
  const now = turns(timeline, time);
  return (
    <figure className="timeline-lanes" aria-label="Timeline lanes">
      {plan !== null && <PlanLane timeline={timeline} entries={plan} cursor={cursor} />}
      {timeline.processes.map((process, index) => {
        const { path, count } = ticks(timeline, index);
        return (
          <div className="timeline-lane" key={process}>
            <span data-testid={`timeline-${process}`}>{`${process}, ${count}`}</span>
            <svg
              viewBox={`0 0 ${CHART_WIDTH} ${HEIGHT}`}
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

// The plan lane's ticks, by what became of each action: carried out, not
// carried out (refused, missed, cancelled, replaced...), still to come.
const PLAN_TICKS = [
  ["ran", (entry: PlanEntry) => entry.resolved && RAN.has(entry.status)],
  ["not-ran", (entry: PlanEntry) => entry.resolved && !RAN.has(entry.status)],
  ["to-come", (entry: PlanEntry) => !entry.resolved],
] as const;

/**
 * A followed run's plan lane (P13.8): each action its plans had in the
 * window as a tick where it started, or was resolved, or falls due, by what
 * became of it; and each listed, in the order of their moments, with its
 * outcome and why; those still to come as soon as they can, last.
 */
function PlanLane({
  timeline,
  entries,
  cursor,
}: {
  timeline: Timeline;
  entries: readonly PlanEntry[];
  cursor: number;
}) {
  const span = timeline.untilS - timeline.fromS;
  const within = entries
    .filter(
      (entry) =>
        entry.timeS === null || (entry.timeS >= timeline.fromS && entry.timeS <= timeline.untilS),
    )
    .sort((a, b) => (a.timeS ?? Number.POSITIVE_INFINITY) - (b.timeS ?? Number.POSITIVE_INFINITY));
  const placed = within.filter((entry) => entry.timeS !== null);
  const column = (timeS: number) =>
    Math.round(((timeS - timeline.fromS) / span) * CHART_WIDTH * TICKS_PER_UNIT) / TICKS_PER_UNIT;
  return (
    <>
      <div className="timeline-lane">
        <span data-testid="timeline-plan">{`plan, ${within.length}`}</span>
        <svg
          viewBox={`0 0 ${CHART_WIDTH} ${HEIGHT}`}
          preserveAspectRatio="none"
          role="img"
          aria-label={`plan: ${within.length} actions`}
        >
          {PLAN_TICKS.map(([name, chosen]) => (
            <path
              key={name}
              className={`timeline-plan-${name}`}
              d={placed
                .filter(chosen)
                .map((entry) => `M${column(entry.timeS ?? 0)} 0V${HEIGHT}`)
                .join("")}
            />
          ))}
          <line className="timeline-now" x1={cursor} x2={cursor} y1={0} y2={HEIGHT} />
        </svg>
      </div>
      {within.length > 0 && (
        <ol className="timeline-plan" aria-label="The run's plan">
          {within.map((entry) => (
            <li
              key={`${entry.planId}/${entry.ref}/${entry.status}`}
              data-testid="timeline-plan-entry"
            >
              {describeEntry(entry)}
            </li>
          ))}
        </ol>
      )}
    </>
  );
}

/** An action of a plan lane, in words: when, what, and what became of it
 * and why, or how it stands. */
export function describeEntry(entry: PlanEntry): string {
  const when = entry.timeS === null ? "as soon as it can" : describeTime(entry.timeS);
  const why = entry.reason === null ? "" : `: ${entry.reason}`;
  return `${when}, ${entry.action} (${entry.planId}/${entry.ref}): ${entry.status}${why}`;
}
