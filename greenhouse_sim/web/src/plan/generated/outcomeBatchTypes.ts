// Generated from ../greenhouse_protocol/greenhouse_protocol/schemas/outcome-batch.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export type Instant = string;
export type Identifier = string;
export type Name = string;
export type ActionId = string;
export type Action = SetLevel | SetTarget | Water | Harvest | Lower | RemoveLeaf | Inspect;
export type ItemName = string;
export type HarvestScope = "ripe" | "fruit" | "truss";
/**
 * Lower a plant's stem: by so many centimetres, by so many internodes,
 * or until its top has so much head room under its wire. Exactly one.
 */
export type Lower = Lower1 & Lower2;
export type Lower1 =
  | {
      by_cm: number;
    }
  | {
      by_internodes: number;
    }
  | {
      to_head_room_m: number;
    };
export type Timing = At | Window | Asap;
export type PrincipalKind = "person" | "policy" | "schedule" | "scenario" | "platform";
export type OutcomeStatus =
  "executed" | "late" | "missed" | "refused" | "failed" | "cancelled" | "superseded" | "unconfirmed";
export type ExecutorKind = "simulated_run" | "person" | "robot" | "climate_computer";
export type ActionEffect = LevelSet | TargetSet | Watered | Harvested | Lowered | LeafRemoved | Inspected;

/**
 * The outcomes delivered after a cursor, in delivery order.
 */
export interface OutcomeBatch {
  run_id: string;
  epoch: number;
  after: number;
  next: number;
  simulated_now: Instant;
  has_more?: boolean;
  outcomes: ActionOutcome[];
}
/**
 * One planned action's end. Its fields agree with its status: an action
 * that ran has its times and its executor; one that never started has
 * neither, and says why; only a cancelled or superseded one names who did
 * it, only a missed one its fallback, only one that ran its effect, which
 * is its action's kind's. `resolved_at`, when the outcome was decided, is
 * always set and orders the log; `due` is None only for an
 * as-soon-as-possible action dropped before it could start.
 */
export interface ActionOutcome {
  outcome_id: Identifier;
  greenhouse_id: Name;
  run_id: Name;
  epoch: number;
  plan_id: Identifier;
  revision: number;
  ref: ActionRef;
  action: Action;
  timing: Timing;
  principal: Principal;
  status: OutcomeStatus;
  due: Instant | Window | null;
  started_at?: Instant | null;
  finished_at?: Instant | null;
  resolved_at: Instant;
  delivered_at?: Instant | null;
  executor?: ExecutorRef | null;
  reason?: string | null;
  cancelled_by?: Principal | null;
  fallback?: ActionRef | null;
  effect?: ActionEffect | null;
  event_id?: Name | null;
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
 * A device's level, from 0 (off) to 1 (full), or `auto` to hand the
 * device back to whatever control loop runs it. A door or vent is a
 * device, its level how far it is open.
 */
export interface SetLevel {
  kind?: "set_level";
  device_id: ItemName;
  level: number | "auto";
}
/**
 * A climate controller's heating setpoint, by day or by night, in °C.
 * Each kind of target has its own unit and range: the venting and humidity
 * targets, when a controller has them, are members of their own beside
 * this one.
 */
export interface SetTarget {
  kind?: "set_target";
  target: "heating_day" | "heating_night";
  value_c: number;
}
export interface Water {
  kind?: "water";
  plant_id: ItemName;
  amount_ml: number;
}
export interface Harvest {
  kind?: "harvest";
  plant_id: ItemName;
  scope: HarvestScope;
  organ_id?: ItemName | null;
}
export interface Lower2 {
  kind?: "lower";
  plant_id: ItemName;
  by_cm?: number | null;
  by_internodes?: number | null;
  to_head_room_m?: number | null;
}
export interface RemoveLeaf {
  kind?: "remove_leaf";
  plant_id: ItemName;
  leaf_id: ItemName;
}
export interface Inspect {
  kind?: "inspect";
  plant_id: ItemName;
  reason: string;
}
/**
 * Due at an instant.
 */
export interface At {
  kind?: "at";
  at: Instant;
}
/**
 * Due between two instants: it starts at the earliest one in them an
 * executor can honour and is free to take.
 */
export interface Window {
  kind?: "window";
  not_before: Instant;
  not_after: Instant;
}
/**
 * As soon as what it waits for is done, before its deadline if it has
 * one.
 */
export interface Asap {
  kind?: "asap";
  deadline?: Instant | null;
}
/**
 * Who asks for an action, by identity: a person, a control policy, a
 * schedule, a scenario's own plan, a platform.
 */
export interface Principal {
  kind: PrincipalKind;
  id: Name;
}
/**
 * Who carries an action out: a kind of executor, and which one, or any
 * of the kind when `id` is None.
 */
export interface ExecutorRef {
  kind: ExecutorKind;
  id?: Name | null;
}
export interface LevelSet {
  kind?: "level_set";
  device_id: Name;
  level: number | "auto";
}
export interface TargetSet {
  kind?: "target_set";
  target: Name;
  value_c: number;
}
export interface Watered {
  kind?: "watered";
  amount_ml: number;
}
export interface Harvested {
  kind?: "harvested";
  fruit_count: number;
  fresh_mass_g: number;
}
export interface Lowered {
  kind?: "lowered";
  by_cm: number;
}
export interface LeafRemoved {
  kind?: "leaf_removed";
  leaf_id: Name;
}
export interface Inspected {
  kind?: "inspected";
}
