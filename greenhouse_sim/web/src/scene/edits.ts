import { DAY_S } from "../clock";

// A target changes on the minute, as the simulator takes it (#274).
const TARGET_EVERY_S = 60;

import type { FieldView, Slice } from "../fields/display";
import { defaultSlice } from "../fields/drawing";
import type { EnvironmentField } from "../fields/field";
import { CLIMATE_FIELD } from "../fields/source";
import type { Point3 } from "../world";
import { type SceneSource, type ScheduledCommand, scheduleText, type TargetChange } from "./source";

/** A scenario's source: what its panels change. */
export type ScenarioSource = Extract<SceneSource, { kind: "scenario" }>;

/** Another of its fields drawn, or none. How the last was drawn goes; its
 * probes stay, and so does what it is compared with, unless that is the
 * field now drawn. */
export function withField(source: ScenarioSource, name: string | null): ScenarioSource {
  const { field: _, fieldView: __, slice: ___, compare, probes, ...rest } = source;
  if (name === null) {
    return rest;
  }
  return {
    ...rest,
    field: name,
    ...(probes === undefined ? {} : { probes }),
    ...(compare === undefined || compare === name ? {} : { compare }),
  };
}

/** Its probes, none left out when there are none. */
export function withProbes(source: ScenarioSource, probes: Point3[]): ScenarioSource {
  const { probes: _, ...rest } = source;
  return probes.length === 0 ? rest : { ...rest, probes };
}

/** Another field compared with the drawn one at the probes, or none. */
export function withCompared(source: ScenarioSource, name: string | null): ScenarioSource {
  const { compare: _, ...rest } = source;
  return name === null ? rest : { ...rest, compare: name };
}

/** The field drawn another way; a slice where it was, or the field's
 * default. */
export function withFieldView(
  source: ScenarioSource,
  view: FieldView,
  field: EnvironmentField,
): ScenarioSource {
  const { slice, ...rest } = source;
  return view === "slice"
    ? { ...rest, fieldView: view, slice: slice ?? defaultSlice(field) }
    : { ...rest, fieldView: view };
}

/** The slice moved, or of another quantity. */
export function withSlice(source: ScenarioSource, slice: Slice): ScenarioSource {
  return { ...source, slice };
}

/** The boundaries a CFD solver is given, drawn or not. */
export function withCfdBoundaries(source: ScenarioSource, show: boolean): ScenarioSource {
  const { cfdBoundaries: _, ...rest } = source;
  return show ? { ...rest, cfdBoundaries: true } : rest;
}

/** Another weather to run under, a preset's by name, or its own. */
export function withWeather(source: ScenarioSource, chosen: string | undefined): ScenarioSource {
  const { weather: _, ...rest } = source;
  return chosen === undefined ? rest : { ...rest, weather: chosen };
}

/** The sky clouded as the QA override asks, or as its weather's own. */
export function withClouds(source: ScenarioSource, clouds: number | undefined): ScenarioSource {
  const { clouds: _, ...rest } = source;
  return clouds === undefined ? rest : { ...rest, clouds };
}

/** Its wind's direction overridden, for QA, or its weather's own. */
export function withWind(source: ScenarioSource, wind: number | undefined): ScenarioSource {
  const { wind: _, ...rest } = source;
  return wind === undefined ? rest : { ...rest, wind };
}

/** How far its doors and vents stand open: while a climate run is drawn
 * past its start, an override at that moment of those that changed, as its
 * equipment's are, so that the run stays the same house, carried on from a
 * checkpoint rather than worked out again from its start; otherwise, from
 * the start. */
export function withOpenings(
  source: ScenarioSource,
  openings: Record<string, number>,
): ScenarioSource {
  const now = source.time ?? 0;
  if (source.field === CLIMATE_FIELD && now > 0) {
    const standing = openingsAt(source, Object.keys(openings));
    const changed = Object.fromEntries(
      Object.entries(openings).filter(([openingId, level]) => standing[openingId] !== level),
    );
    return { ...source, schedule: withOverride(source.schedule ?? [], now, changed) };
  }
  return { ...source, openings };
}

/** A moment of its climate run; 0, its start, is left out. */
export function withTime(source: ScenarioSource, seconds: number): ScenarioSource {
  const { time: _, ...rest } = source;
  return seconds > 0 ? { ...rest, time: seconds } : rest;
}

/** Its run's targets changed to `targets` from the moment drawn on, or the
 * next minute if it lies between two, where a target changes (#274). */
export function withTargetsSet(
  source: ScenarioSource,
  targets: Readonly<Record<string, number>>,
): ScenarioSource {
  const at = Math.ceil((source.time ?? 0) / TARGET_EVERY_S) * TARGET_EVERY_S;
  const added = Object.entries(targets).map(([target, valueC]) => ({ timeS: at, target, valueC }));
  return withTargets(source, [...(source.targets ?? []), ...added]);
}

/** Its run's target changes as `changes` are: none, if there are none
 * (#274). */
export function withTargets(
  source: ScenarioSource,
  changes: readonly TargetChange[],
): ScenarioSource {
  const { targets: _, ...rest } = source;
  return changes.length === 0 ? rest : { ...rest, targets: [...changes] };
}

/** Its equipment set: while a climate run is drawn past its start, an
 * override at that moment of what changed; otherwise, from the start. */
export function withLevels(source: ScenarioSource, levels: Record<string, number>): ScenarioSource {
  const now = source.time ?? 0;
  if (source.field === CLIMATE_FIELD && now > 0) {
    const standing = levelsAt(source);
    const changed = Object.fromEntries(
      Object.entries(levels).filter(([actuatorId, level]) => standing[actuatorId] !== level),
    );
    return { ...source, schedule: withOverride(source.schedule ?? [], now, changed) };
  }
  return { ...source, levels };
}

/** Its schedule without one of its commands, none left out when none are
 * left. */
export function withoutCommand(source: ScenarioSource, index: number): ScenarioSource {
  const { schedule: _, ...rest } = source;
  const schedule = (source.schedule ?? []).filter((__, at) => at !== index);
  return schedule.length === 0 ? rest : { ...rest, schedule };
}

/** Its daily commands without one of them; with none left, it says so,
 * rather than fall back on its scenario's own. */
export function withoutDaily(source: ScenarioSource, index: number): ScenarioSource {
  return { ...source, daily: (source.daily ?? []).filter((_, at) => at !== index) };
}

/** One of its commands repeated every day, at its time of day, in place of
 * the one command: the last of its daily commands. */
export function withRepeated(source: ScenarioSource, index: number): ScenarioSource {
  const command = source.schedule?.[index];
  if (command === undefined) {
    return source;
  }
  const repeated = { ...command, timeS: command.timeS % DAY_S };
  return { ...withoutCommand(source, index), daily: [...(source.daily ?? []), repeated] };
}

/** A scenario's source with its scenario's own daily commands, `own`, where
 * it gives none of its own (P09.4). */
export function withOwnDaily<S extends { daily?: ScheduledCommand[] }>(
  source: S,
  own: readonly ScheduledCommand[],
): S {
  return source.daily === undefined && own.length > 0 ? { ...source, daily: [...own] } : source;
}

/** A scenario's source keeping its daily commands only where they differ
 * from its scenario's own, `own`: the address keeps a change, not a copy. */
export function keptDaily<S extends { daily?: ScheduledCommand[] }>(
  source: S,
  own: readonly ScheduledCommand[],
): S {
  if (source.daily === undefined || scheduleText(source.daily) !== scheduleText(own)) {
    return source;
  }
  const { daily: _, ...rest } = source;
  return rest as S;
}

/** A daily command's latest moment by `now`, in seconds into the run, or
 * null if its time of day has not yet come on the run's first day. */
export function latestDaily(command: ScheduledCommand, now: number): number | null {
  return now < command.timeS
    ? null
    : Math.floor((now - command.timeS) / DAY_S) * DAY_S + command.timeS;
}

/** A scenario's equipment's levels at the moment of its climate run drawn:
 * those set from the start, then its commands up to that moment, in time
 * order, the later winning at a moment; its daily commands at a moment
 * before the others then, as the simulator applies them. */
export function levelsAt(source: {
  levels?: Readonly<Record<string, number>>;
  schedule?: readonly ScheduledCommand[];
  daily?: readonly ScheduledCommand[];
  time?: number;
}): Record<string, number> {
  const now = source.time ?? 0;
  const levels: Record<string, number> = { ...(source.levels ?? {}) };
  const daily = (source.daily ?? []).flatMap((command) => {
    const timeS = latestDaily(command, now);
    return timeS === null ? [] : [{ ...command, timeS }];
  });
  const applied = [...daily, ...(source.schedule ?? [])]
    .map((command, order) => ({ command, order }))
    .filter(({ command }) => command.timeS <= now)
    .sort((a, b) => a.command.timeS - b.command.timeS || a.order - b.order);
  for (const { command } of applied) {
    levels[command.actuatorId] = command.level;
  }
  return levels;
}

/** How far each of `openingIds` stands open at the moment drawn, as the
 * source says: from the start, as its openings set them, then as its
 * commands to them do. One the source says nothing of is left out. */
export function openingsAt(
  source: {
    levels?: Readonly<Record<string, number>>;
    openings?: Readonly<Record<string, number>>;
    schedule?: readonly ScheduledCommand[];
    daily?: readonly ScheduledCommand[];
    time?: number;
  },
  openingIds: readonly string[],
): Record<string, number> {
  const commanded = levelsAt(source);
  const standing: Record<string, number> = { ...(source.openings ?? {}) };
  for (const openingId of openingIds) {
    const level = commanded[openingId];
    if (level !== undefined) {
      standing[openingId] = level;
    }
  }
  return standing;
}

/** The schedule with an override at a moment: each actuator's command at
 * that moment replaced by the level it is set to, kept in time order. */
export function withOverride(
  schedule: readonly ScheduledCommand[],
  timeS: number,
  levels: Readonly<Record<string, number>>,
): ScheduledCommand[] {
  const kept = schedule.filter(
    (command) => !(command.timeS === timeS && command.actuatorId in levels),
  );
  const added = Object.entries(levels).map(([actuatorId, level]) => ({ timeS, actuatorId, level }));
  return [...kept, ...added]
    .map((command, order) => ({ command, order }))
    .sort((a, b) => a.command.timeS - b.command.timeS || a.order - b.order)
    .map(({ command }) => command);
}

/** A scenario's source with its equipment, and its doors and vents,
 * `openingIds`, at the levels they stand at at the moment drawn: its
 * commands to an opening open it that far, as the simulator's do; and the
 * levels `governed` by a thermostat as the run has them. */
export function standingAt<
  S extends {
    levels?: Readonly<Record<string, number>>;
    openings?: Readonly<Record<string, number>>;
    schedule?: readonly ScheduledCommand[];
    daily?: readonly ScheduledCommand[];
    time?: number;
  },
>(source: S, openingIds: readonly string[], governed: Readonly<Record<string, number>> = {}): S {
  const doors = new Set(openingIds);
  const standing = Object.entries({ ...levelsAt(source), ...governed });
  return {
    ...source,
    levels: Object.fromEntries(standing.filter(([id]) => !doors.has(id))),
    openings: {
      ...(source.openings ?? {}),
      ...Object.fromEntries(standing.filter(([id]) => doors.has(id))),
    },
  };
}

/** The scenario on show with another of its layouts keeps the weather it is
 * run under, and how its air is drawn, probed and compared, so that the two
 * layouts' air can be compared; any other choice starts afresh. */
export function withItsAir(shown: SceneSource, chosen: SceneSource): SceneSource {
  if (
    shown.kind !== "scenario" ||
    chosen.kind !== "scenario" ||
    shown.scenarioId !== chosen.scenarioId
  ) {
    return chosen;
  }
  const { weather, clouds, wind, field, fieldView, slice, compare, probes, cfdBoundaries } = shown;
  return {
    ...chosen,
    ...(weather === undefined ? {} : { weather }),
    ...(clouds === undefined ? {} : { clouds }),
    ...(wind === undefined ? {} : { wind }),
    ...(field === undefined ? {} : { field }),
    ...(fieldView === undefined ? {} : { fieldView }),
    ...(slice === undefined ? {} : { slice }),
    ...(compare === undefined ? {} : { compare }),
    ...(probes === undefined ? {} : { probes }),
    ...(cfdBoundaries === undefined ? {} : { cfdBoundaries }),
  };
}
