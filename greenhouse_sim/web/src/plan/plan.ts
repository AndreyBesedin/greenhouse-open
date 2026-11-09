/**
 * The actions the viewer asks of a run (P13.8, decision 0046): what a person
 * sets in its panels, a device's level or a heating target, or asks of a
 * plant, as the local operator's. A replay asks them of its epoch while it is
 * computed, through its changes (P22.1), or of a fork once it has ended.
 */

import type { LabAction } from "../plants/lab";
import type { Action, Principal } from "./generated/planTypes";

/** Whom the simulator's local API takes every write from (decision 0052). */
export const LOCAL_OPERATOR: Principal = { kind: "person", id: "local_operator" };

/** What became of actions given: taken into the run's plan, from the moment
 * it says if the run says one, or refused, and why, in the run's words. */
export type Given = { status: "given"; atS?: number } | { status: "refused"; reason: string };

/** A level for a device, its equipment's or a door's or vent's. */
export function setLevel(deviceId: string, level: number): Action {
  return { kind: "set_level", device_id: deviceId, level };
}

/** A heating target, `heating_day` or `heating_night`, in °C. */
export function setTarget(target: string, valueC: number): Action {
  return { kind: "set_target", target: target as "heating_day", value_c: valueC };
}

/** The protocol's action a plant's button asks for, as the plant lab names
 * it: a leaf removed, a fruit or a truss harvested, the stem lowered by so
 * many internodes. */
export function cropAction({ plantId, kind, target }: LabAction): Action {
  switch (kind) {
    case "remove_leaf":
      return { kind: "remove_leaf", plant_id: plantId, leaf_id: target };
    case "harvest_fruit":
      return { kind: "harvest", plant_id: plantId, scope: "fruit", organ_id: target };
    case "harvest_truss":
      return { kind: "harvest", plant_id: plantId, scope: "truss", organ_id: target };
    case "lower_stem":
      return { kind: "lower", plant_id: plantId, by_internodes: Number(target) };
  }
}
