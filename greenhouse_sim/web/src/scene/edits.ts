import { DAY_S } from "../clock";
import type { FieldView, Slice } from "../fields/display";
import { defaultSlice } from "../fields/drawing";
import type { EnvironmentField } from "../fields/field";
import { CLIMATE_FIELD } from "../fields/source";
import type { Point3 } from "../world";
import { levelsAt, openingsAt, type SceneSource, type TargetChange, withOverride } from "./source";

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
