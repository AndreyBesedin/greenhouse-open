// Generated from ../greenhouse_protocol/greenhouse_protocol/schemas/action-state.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export type Identifier = string;
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
export type PrincipalKind = "person" | "policy" | "schedule" | "scenario" | "platform";
export type Name = string;
export type ActionStateKind = "waiting" | "due" | "assigned" | "started";

/**
 * An action not yet resolved, as it stands: what a gateway lists. Once
 * resolved, it is an outcome in the outcome log, not a state.
 */
export interface ActionState {
  plan_id: Identifier;
  revision: number;
  ref: ActionRef;
  action: Action;
  timing: Timing;
  due?: Instant | Window | null;
  principal: Principal;
  state: ActionStateKind;
  waiting_for?: ActionRef[];
  waited_on_by?: ActionRef[];
  carried_from?: RunEpoch | null;
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
export interface RunEpoch {
  run_id: string;
  epoch: number;
}
