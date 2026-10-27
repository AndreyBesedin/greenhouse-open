// Generated from ../greenhouse_protocol/greenhouse_protocol/schemas/receipt.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export type Identifier = string;
export type ActionId = string;

/**
 * A gateway's answer to a write. A request refused whole has its
 * errors and changed nothing; one accepted lists what it refused at once,
 * what it cancelled, and the keys it would not act on.
 */
export interface Receipt {
  accepted: boolean;
  plan_id?: Identifier | null;
  revision?: number | null;
  sequence?: number | null;
  errors?: string[];
  refused?: ActionRef[];
  cancelled?: ActionRef[];
  stale?: ActionKey[];
  not_permitted?: ActionKey[];
}
/**
 * Which action a record is about: a planned action, one occurrence of a
 * recurring one, or the fallback carried out in its place. `str()` spells
 * it for people, `harvest@3` or `vent/fallback`; records keep the parts.
 */
export interface ActionRef {
  action_id: ActionId;
  occurrence?: number | null;
  fallback?: boolean;
}
/**
 * An action as a caller saw it, to cancel it: in a plan, a revision and
 * an epoch. A key whose action a later revision replaced, or whose epoch
 * has ended, is stale: refused, and nothing cancelled. An occurrence of
 * None, for a recurring action, means every occurrence still to come.
 */
export interface ActionKey {
  plan_id: Identifier;
  epoch: number;
  revision: number;
  ref: ActionRef;
}
