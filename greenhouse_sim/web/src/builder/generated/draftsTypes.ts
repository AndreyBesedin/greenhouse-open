// Generated from greenhouse_sim/services/drafts.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export type DraftsListed = DraftListed[];

/**
 * A draft as a list of them shows it: its latest revision.
 */
export interface DraftListed {
  draft_id: string;
  name: string;
  revision: number;
  saved_at: string;
}
