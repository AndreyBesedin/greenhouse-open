import { useEffect } from "react";

import { DEFAULT_LAYOUT } from "../scenarios";
import { withTargets, withTime } from "./edits";
import { sameLayout } from "./moves";
import { followedMoment, usePlayback } from "./playback";
import { type SceneSource, targetsFrom, targetsText } from "./source";
import type { SetSource } from "./useSource";

type ScenarioOf<S> = Extract<S, { kind: "scenario" }>;

/**
 * A run followed as it is played back (P10.2, decision 0041): the moment
 * drawn is the playback's clock, in whole minutes, moved on once the moment
 * asked for before has arrived, so that a slow day is never skipped past
 * half drawn; the run's own play stands aside (`onClockMoved`). A moment
 * whose field failed (`fieldFailed`) has arrived as far as it will: the view
 * moves on with the clock, and asks for the next, rather than wait on it.
 *
 * Followed, the run drawn changes its targets as the run played back does
 * (#274, decision 0043), so that every part of it is asked for with them.
 * `anotherRun` says what the view's address (`addressed`) changes of the run
 * played back, which makes the run drawn another.
 */
export function useFollow({
  source,
  addressed,
  setSource,
  drawingField,
  fieldShownMoment,
  fieldFailed,
  onClockMoved,
}: {
  source: SceneSource;
  addressed: SceneSource;
  setSource: (change: SetSource) => void;
  drawingField: boolean;
  fieldShownMoment: number | null;
  fieldFailed: boolean;
  onClockMoved: () => void;
}) {
  const followed = source.kind === "scenario" && source.follow ? source.scenarioId : null;
  const [playback, setPlayback] = usePlayback(followed);
  const clockMoment = playback.status === "loaded" ? followedMoment(playback.state) : null;
  const askedMoment = source.kind === "scenario" ? (source.time ?? 0) : null;
  useEffect(() => {
    if (followed === null || clockMoment === null || clockMoment === askedMoment) {
      return;
    }
    if (drawingField && fieldShownMoment !== askedMoment && !fieldFailed) {
      return;
    }
    onClockMoved();
    setSource((current) =>
      current.kind === "scenario" ? withTime(current, clockMoment) : current,
    );
  }, [
    followed,
    clockMoment,
    askedMoment,
    fieldShownMoment,
    drawingField,
    fieldFailed,
    onClockMoved,
    setSource,
  ]);
  const playedTargets = playback.status === "loaded" ? targetsText(playback.state.targets) : null;
  useEffect(() => {
    if (followed === null || playedTargets === null) {
      return;
    }
    setSource((current) =>
      current.kind === "scenario" && targetsText(current.targets) !== playedTargets
        ? withTargets(current, targetsFrom(playedTargets) ?? [])
        : current,
    );
  }, [followed, playedTargets, setSource]);
  // What the view changes of the scenario's own run, which is the one
  // played back: any of these makes it another run.
  const playedLayout = playback.status === "loaded" ? playback.state.layout : DEFAULT_LAYOUT;
  const anotherRun =
    addressed.kind === "scenario" && followed !== null ? runChanges(addressed, playedLayout) : [];
  return { followed, playback, setPlayback, playedLayout, anotherRun };
}

/** What a view's address changes of the run played back, its scenario's own
 * with `played` for its layout (#271), in words: each makes the run drawn
 * another than the one played back. */
export function runChanges(source: ScenarioOf<SceneSource>, played: string): string[] {
  const changes: [boolean, string][] = [
    [!sameLayout(source.layout, played, DEFAULT_LAYOUT), "its layout"],
    [source.weather !== undefined, "its weather"],
    [source.clouds !== undefined, "its clouds"],
    [source.wind !== undefined, "its wind"],
    [(source.schedule?.length ?? 0) > 0, "its commands"],
    [source.daily !== undefined, "its daily commands"],
    [source.levels !== undefined, "its equipment"],
    [source.openings !== undefined, "its openings"],
    [source.envelope !== undefined, "its dimensions"],
  ];
  return changes.filter(([changed]) => changed).map(([, said]) => said);
}

/** A view of the run played back, its scenario's own with `played` for its
 * layout: without what would make it another. */
export function withoutRunChanges(source: SceneSource, played: string): SceneSource {
  if (source.kind !== "scenario") {
    return source;
  }
  const {
    layout: _layout,
    weather: _weather,
    clouds: _clouds,
    wind: _wind,
    schedule: _schedule,
    daily: _daily,
    levels: _levels,
    openings: _openings,
    envelope: _envelope,
    ...own
  } = source;
  return sameLayout(played, undefined, DEFAULT_LAYOUT) ? own : { ...own, layout: played };
}
