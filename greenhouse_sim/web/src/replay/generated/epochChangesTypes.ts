// Generated from greenhouse_sim/services/epoch_changes.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export type Status = "queued" | "running" | "finished" | "failed" | "interrupted";
export type JsonValue = unknown;

/**
 * What has become of the changes asked of an epoch: those logged, in
 * order, those refused, and those no worker has taken yet. An epoch that has
 * ended takes no more: whatever is still waiting then is never taken.
 */
export interface EpochChanges {
  status: Status;
  log: LogEntry[];
  refused: Answer[];
  waiting: string[];
}
/**
 * A change given to an epoch while it ran: its number in the log, the
 * instant it takes effect, the moment of the epoch's clock it was given at,
 * who gave it, what it is, and the request it answers if it was asked for
 * through the store. It is applied again at the moment it was given, so
 * that the epoch it makes is the same whenever it is worked out.
 */
export interface LogEntry {
  seq: number;
  at_s: number;
  given_s: number;
  by: string;
  what: {
    [k: string]: JsonValue;
  };
  request: string | null;
}
/**
 * Why a worker did not act on a request it took, in its own words.
 */
export interface Answer {
  request: string;
  reason: string;
}
