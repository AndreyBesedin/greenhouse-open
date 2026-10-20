import { formatValue } from "./readouts";
import type { ThermostatAt } from "./scene/equipment";
import type { SceneEntityKind, SceneSnapshot } from "./scene/generated/snapshotTypes";

// The sliders move in steps of 5%.
const PERCENT = 100;
const STEP_PERCENT = 5;
const WATTS_PER_KILOWATT = 1000;

/** What a kind of equipment does at full power, as its readout says it: the
 * rated property, the factor to the unit shown, and that unit. */
const RATINGS: Partial<Record<SceneEntityKind, { property: string; scale: number; unit: string }>> =
  {
    FAN: { property: "flow_m3_s", scale: 1, unit: "m³/s" },
    HEATER: { property: "power_w", scale: 1 / WATTS_PER_KILOWATT, unit: "kW" },
    DEHUMIDIFIER: { property: "removal_kg_h", scale: 1, unit: "kg/h" },
  };

interface EquipmentState {
  actuatorId: string;
  label: string;
  level: number;
  /** What it does at full power, in `unit`. */
  rated: number;
  unit: string;
}

/** The climate equipment a scene holds, with the level each runs at. */
export function equipmentIn(snapshot: SceneSnapshot): EquipmentState[] {
  return snapshot.entities.flatMap((entity) => {
    const rating = RATINGS[entity.kind];
    const { actuator_id, level } = entity.properties;
    const rated = rating === undefined ? undefined : entity.properties[rating.property];
    if (
      rating === undefined ||
      typeof actuator_id !== "string" ||
      typeof level !== "number" ||
      typeof rated !== "number"
    ) {
      return [];
    }
    return [
      {
        actuatorId: actuator_id,
        label: entity.label ?? actuator_id,
        level,
        rated: rated * rating.scale,
        unit: rating.unit,
      },
    ];
  });
}

/** What a piece of equipment does at its level: off, or its level and what
 * that gives, `50%, 5 kW`. */
export function describeLevel({ level, rated, unit }: EquipmentState): string {
  return level === 0
    ? "off"
    : `${Math.round(level * PERCENT)}%, ${formatValue(level * rated)} ${unit}`;
}

/** What a piece of equipment does, and, if a thermostat runs it, at what it
 * aims: `100%, 30 kW, by its thermostat at 16 °C`. */
export function describeRun(piece: EquipmentState, thermostat: ThermostatAt | null): string {
  const level = describeLevel(piece);
  return thermostat?.actuatorId === piece.actuatorId
    ? `${level}, by its thermostat at ${formatValue(thermostat.setpointC)} °C`
    : level;
}

/**
 * A switch and a slider per piece of equipment. Switched on, a piece runs at
 * full power, and the slider sets its level; either asks the simulator for
 * the scene with that level set, so the scene shown says how hard each runs.
 * A heater a thermostat runs says so; a command to it takes it over.
 */
export function EquipmentControls({
  snapshot,
  requested,
  thermostat = null,
  onChange,
}: {
  snapshot: SceneSnapshot;
  /** The levels asked for, which a control shows until the scene catches up. */
  requested: Readonly<Record<string, number>>;
  /** The thermostat that runs its heater at the moment drawn, if one does. */
  thermostat?: ThermostatAt | null;
  onChange: (levels: Record<string, number>) => void;
}) {
  const equipment = equipmentIn(snapshot);
  if (equipment.length === 0) {
    return null;
  }
  return (
    <fieldset className="equipment-controls" aria-label="Equipment">
      {equipment.map((piece) => {
        const shown = requested[piece.actuatorId] ?? piece.level;
        const set = (level: number) => onChange({ ...requested, [piece.actuatorId]: level });
        return (
          <div key={piece.actuatorId} className="equipment-control">
            <label className="equipment-switch">
              <input
                type="checkbox"
                checked={shown > 0}
                onChange={(event) => set(event.target.checked ? 1 : 0)}
              />{" "}
              {piece.label}
            </label>
            <input
              type="range"
              aria-label={`${piece.label} level`}
              min={0}
              max={PERCENT}
              step={STEP_PERCENT}
              value={Math.round(shown * PERCENT)}
              onChange={(event) => set(Number(event.target.value) / PERCENT)}
            />
            <span data-testid={`equipment-${piece.actuatorId}`}>
              {describeRun(piece, thermostat)}
            </span>
          </div>
        );
      })}
    </fieldset>
  );
}
