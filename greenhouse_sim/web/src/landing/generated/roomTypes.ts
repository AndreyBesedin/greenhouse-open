// Generated from greenhouse_sim/services/room.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

/**
 * What a simulator has room for as a run is asked for (decision 0067): its
 * workers busy and the runs waiting for one, each beside its limit, and what is
 * free on the run store's disk beside the floor a run begins above. A limit of
 * none is no limit, and a store that cannot say what is free says none.
 * `refusal` is what a run, a resume or a fork asked for now would be refused
 * with, in the words of that refusal, or none if it would be let in.
 */
export interface Room {
  workers_busy: number;
  workers_limit: number;
  runs_waiting: number;
  runs_waiting_limit: number | null;
  disk_free_bytes: number | null;
  disk_free_limit_bytes: number | null;
  refusal: string | null;
}
