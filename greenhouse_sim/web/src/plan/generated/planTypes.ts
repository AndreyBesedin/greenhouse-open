// Generated from ../greenhouse_protocol/greenhouse_protocol/schemas/plan.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

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
export type Instant = string;
/**
 * Every `period`, `count` times or until an instant: occurrence `n`,
 * from 0, is the planned action's timing moved by `n` periods. The timing
 * is its one anchor.
 */
export type Recurrence = Recurrence1 & Recurrence2;
export type Recurrence1 =
  | {
      count: number;
    }
  | {
      until: string;
    };
export type IfPrerequisiteFails = "cancel" | "proceed";
/**
 * What a gateway does with an action that cannot start by its due
 * instant and tolerance.
 */
export type OnLate = "run_late" | "skip" | "critical" | "fallback" | "abort_plan";
export type ExecutorKind = "simulated_run" | "person" | "robot" | "climate_computer";
export type PrincipalKind = "person" | "policy" | "schedule" | "scenario" | "platform";

/**
 * The actions a run is to carry out, given in one of its epochs as one
 * revision of a plan. A revision replaces, from an instant on, the actions
 * of the one before that have not started (the gateway's rule).
 *
 * Checked as made: action ids unique, every prerequisite in the plan, no
 * cycle. Edges between recurring actions pair their occurrences, so two
 * recurring actions may wait for one another only if they recur alike,
 * occurrence `n` for occurrence `n`; a recurring action may wait for a
 * one-off one, each occurrence for it; a one-off action may not wait for a
 * recurring one, since which occurrence is meant is not said. With those
 * edges the plan, expanded occurrence by occurrence, has a cycle only if it
 * has one as given, so it is checked as given.
 */
export interface Plan {
  plan_id: Identifier;
  run_id: Name;
  epoch: number;
  revision: number;
  actions: PlannedAction[];
}
export interface PlannedAction {
  action_id: ActionId;
  action: Action;
  timing: Timing;
  every?: Recurrence | null;
  after?: ActionId[];
  if_prerequisite_fails?: IfPrerequisiteFails;
  lateness?: Lateness;
  expected_duration_s?: number | null;
  executed_by?: ExecutorRef[] | null;
  proposed_by: Principal;
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
export interface Recurrence2 {
  period: string;
  count?: number | null;
  until?: Instant | null;
}
export interface Lateness {
  tolerance_s?: number;
  on_late?: OnLate;
  fallback?: Action | null;
}
/**
 * Who carries an action out: a kind of executor, and which one, or any
 * of the kind when `id` is None.
 */
export interface ExecutorRef {
  kind: ExecutorKind;
  id?: Name | null;
}
/**
 * Who asks for an action, by identity: a person, a control policy, a
 * schedule, a scenario's own plan, a platform.
 */
export interface Principal {
  kind: PrincipalKind;
  id: Name;
}
