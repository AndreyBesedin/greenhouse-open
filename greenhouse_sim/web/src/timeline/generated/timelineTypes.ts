// Generated from greenhouse_sim/services/timeline.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

/**
 * A run's events from `from_s` to `until_s`, in the order they happen,
 * column by column.
 */
export interface TimelineDocument {
  from_s: number;
  until_s: number;
  processes: string[];
  subjects: string[];
  kinds: string[];
  times_s: number[];
  process: number[];
  subject: number[];
  kind: number[];
}
