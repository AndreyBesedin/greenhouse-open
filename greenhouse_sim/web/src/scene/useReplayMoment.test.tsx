// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import { type Rendered, render } from "../testing/render";
import type { SceneSource } from "./source";
import { replayedMoment, useReplayMoment } from "./useReplayMoment";
import type { SetSource } from "./useSource";

const SOURCE: SceneSource = { kind: "scenario", scenarioId: "climate_box", field: "climate" };

interface Props {
  momentS: number | null;
  source?: SceneSource;
  drawingField?: boolean;
  fieldShownMoment?: number | null;
  fieldFailed?: boolean;
}

describe("the moment a replay draws", () => {
  let rendered: Rendered | undefined;
  afterEach(() => rendered?.unmount());

  function Probe(props: Props & { setSource: (change: SetSource) => void; onMoved: () => void }) {
    useReplayMoment({
      momentS: props.momentS,
      source: props.source ?? SOURCE,
      setSource: props.setSource,
      drawingField: props.drawingField ?? false,
      fieldShownMoment: props.fieldShownMoment ?? null,
      fieldFailed: props.fieldFailed ?? false,
      onClockMoved: props.onMoved,
    });
    return null;
  }

  function shown(props: Props) {
    const setSource = vi.fn();
    const onMoved = vi.fn();
    rendered = render(<Probe {...props} setSource={setSource} onMoved={onMoved} />);
    /** The source the last change makes of the one drawn. */
    const made = (): SceneSource | undefined => {
      const change = setSource.mock.calls.at(-1)?.[0] as SetSource | undefined;
      return typeof change === "function" ? change(props.source ?? SOURCE) : change;
    };
    return { setSource, onMoved, made, props };
  }

  it("is a whole minute", () => {
    expect(replayedMoment(3601)).toBe(3600);
    expect(replayedMoment(59.9)).toBe(0);
  });

  it("draws the position's moment, and the run's own play stands aside", () => {
    const { made, onMoved } = shown({ momentS: 7200 });

    expect(made()).toMatchObject({ kind: "scenario", time: 7200 });
    expect(onMoved).toHaveBeenCalledOnce();
  });

  it("does nothing while there is no position, or the moment is already drawn", () => {
    expect(shown({ momentS: null }).setSource).not.toHaveBeenCalled();
    rendered?.unmount();
    const drawn: SceneSource = { ...SOURCE, time: 7200 } as SceneSource;
    expect(shown({ momentS: 7200, source: drawn }).setSource).not.toHaveBeenCalled();
  });

  it("waits for the field of the moment asked for before moving on", () => {
    const waiting = shown({
      momentS: 7200,
      source: { ...SOURCE, time: 3600 } as SceneSource,
      drawingField: true,
      fieldShownMoment: 0,
    });
    expect(waiting.setSource).not.toHaveBeenCalled();
    rendered?.unmount();

    const arrived = shown({
      momentS: 7200,
      source: { ...SOURCE, time: 3600 } as SceneSource,
      drawingField: true,
      fieldShownMoment: 3600,
    });
    expect(arrived.setSource).toHaveBeenCalledOnce();
  });

  it("moves on when the field of the moment asked for failed, as it will not arrive", () => {
    const failed = shown({
      momentS: 7200,
      source: { ...SOURCE, time: 3600 } as SceneSource,
      drawingField: true,
      fieldShownMoment: 0,
      fieldFailed: true,
    });

    expect(failed.setSource).toHaveBeenCalledOnce();
  });

  it("changes only a scenario's source", () => {
    const { setSource } = shown({ momentS: 60, source: { kind: "example" } });

    expect(setSource).not.toHaveBeenCalled();
  });
});
