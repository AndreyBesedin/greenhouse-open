import { DAY_S } from "../clock";
import { contractReader, loadJson } from "../loadJson";
import { type RunParts, runParameters, scenarioUrl } from "../scene/run";
import { TIMELINE_SCHEMA } from "./generated/timelineSchema";
import type { TimelineDocument } from "./generated/timelineTypes";

/** A run's events in a window, in the order they happen, column by column,
 * as the simulator serves them (`GET /api/scenarios/{id}/timeline`): each
 * one's moment, and the index of its process, subject and kind. */
export interface Timeline {
  fromS: number;
  untilS: number;
  /** In the order they take their turns at a moment. */
  processes: string[];
  subjects: string[];
  kinds: string[];
  timesS: number[];
  process: number[];
  subject: number[];
  kind: number[];
}

export type TimelineState =
  | { status: "none" }
  | { status: "loading" }
  | { status: "unavailable"; reason: string }
  | { status: "loaded"; timeline: Timeline };

/** How much of a run the timeline shows, to choose from: from a day to a
 * minute. */
export const ZOOMS: readonly { spanS: number; label: string }[] = [
  { spanS: DAY_S, label: "a day" },
  { spanS: 3600, label: "an hour" },
  { spanS: 600, label: "10 min" },
  { spanS: 60, label: "a minute" },
];

/** The window of a zoom's span a moment belongs to: the one it lies in, or,
 * at its end, the one it ends, as a day is on the run's clock (`../clock`).
 * Every span divides a day, so a window lies within a day. */
export function timelineWindow(seconds: number, spanS: number): { fromS: number; untilS: number } {
  const index = Math.max(0, Math.ceil(seconds / spanS) - 1);
  return { fromS: index * spanS, untilS: (index + 1) * spanS };
}

/** Where a run's timeline in a window is published, asked for as its
 * climate is: its layout, its equipment's levels and its commands. */
export function timelineUrl(
  scenarioId: string,
  run: RunParts,
  window: { fromS: number; untilS: number },
): string {
  return scenarioUrl(scenarioId, "timeline", [
    ...runParameters(run, ["layout", "levels", "schedule", "daily", "targets"]),
    `from=${window.fromS}`,
    `t=${window.untilS}`,
  ]);
}

const UNEXPECTED = "the timeline is not what the viewer expects";
const readTimeline = contractReader<TimelineDocument>(TIMELINE_SCHEMA, UNEXPECTED);

/** A timeline, checked rather than trusted: each event with its process,
 * subject and kind. */
export function parseTimeline(body: unknown): Timeline {
  const timeline = readTimeline(body);
  const events = timeline.times_s.length;
  if (
    [timeline.process, timeline.subject, timeline.kind].some((column) => column.length !== events)
  ) {
    throw new Error(UNEXPECTED);
  }
  return {
    fromS: timeline.from_s,
    untilS: timeline.until_s,
    processes: timeline.processes,
    subjects: timeline.subjects,
    kinds: timeline.kinds,
    timesS: timeline.times_s,
    process: timeline.process,
    subject: timeline.subject,
    kind: timeline.kind,
  };
}

/** Fetches a run's timeline; every failure becomes a state. */
export async function loadTimeline(
  url: string,
  fetchFn: typeof fetch = fetch,
): Promise<TimelineState> {
  const answer = await loadJson(url, parseTimeline, fetchFn);
  return answer.status === "loaded" ? { status: "loaded", timeline: answer.value } : answer;
}

/** One event of a timeline, by name. */
export interface TimelineEvent {
  timeS: number;
  process: string;
  subject: string;
  kind: string;
}

/** A timeline's events at a moment, in the order they happen then. */
export function eventsAt(timeline: Timeline, seconds: number): TimelineEvent[] {
  const found: TimelineEvent[] = [];
  for (const [at, timeS] of timeline.timesS.entries()) {
    if (timeS === seconds) {
      found.push({
        timeS,
        process: timeline.processes[timeline.process[at] ?? 0] ?? "",
        subject: timeline.subjects[timeline.subject[at] ?? 0] ?? "",
        kind: timeline.kinds[timeline.kind[at] ?? 0] ?? "",
      });
    }
  }
  return found;
}

// A process's events at a moment are named one by one up to this many.
const FEW = 3;

/** What a process does at a moment, in words: each of its events, or, for
 * more than a few, how many of each kind (`13 × sample`). */
export function describeTurn(events: readonly TimelineEvent[]): string {
  if (events.length <= FEW) {
    return events.map(({ subject, kind }) => `${subject} ${kind}`).join(", ");
  }
  const counts = new Map<string, number>();
  for (const { kind } of events) {
    counts.set(kind, (counts.get(kind) ?? 0) + 1);
  }
  return [...counts].map(([kind, count]) => `${count} × ${kind}`).join(", ");
}
