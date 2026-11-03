// @vitest-environment jsdom
import type { ComponentProps } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CLIMATE_FIELD } from "./fields/source";
import { ScenarioPanels } from "./ScenarioPanels";
import type { SceneSnapshot } from "./scene/generated/snapshotTypes";
import { button, click, type Rendered, render, said } from "./testing/render";

// What the weather offers is said by what it is given to do.
vi.mock("./weather/WeatherPanel", () => ({
  WeatherPanel: ({ onChoose, onClouds, onWindFrom }: Record<string, unknown>) => (
    <p data-testid="weather-offers">
      {[onChoose, onClouds, onWindFrom].filter((given) => given !== undefined).length}
    </p>
  ),
}));

const LOADS = {
  field: { status: "loading" },
  compared: { status: "none" },
  weather: { status: "loading" },
  weatherDay: { status: "loading" },
  houseAir: { status: "loading" },
  probeCharts: { status: "loading" },
  cfd: { status: "none" },
} as unknown as ComponentProps<typeof ScenarioPanels>["loads"];

const SNAPSHOT = { entities: [], greenhouse_id: "box" } as unknown as SceneSnapshot;

function panels(more: Partial<ComponentProps<typeof ScenarioPanels>> = {}) {
  return render(
    <ScenarioPanels
      source={{
        kind: "scenario",
        scenarioId: "box",
        field: CLIMATE_FIELD,
        schedule: [{ timeS: 60, actuatorId: "heater", level: 0.5 }],
      }}
      snapshot={SNAPSHOT}
      weathers={["default", "cold"]}
      days={3}
      loads={LOADS}
      fieldView="arrows"
      fieldSlice={null}
      probes={[]}
      placing={false}
      probeHeight={1}
      playingClimate={false}
      onSource={vi.fn()}
      onProbes={vi.fn()}
      onPlacing={vi.fn()}
      onProbeHeight={vi.fn()}
      onPlayingClimate={vi.fn()}
      onOwnRange={vi.fn()}
      {...more}
    />,
  );
}

describe("a stored run's panels", () => {
  let rendered: Rendered | undefined;
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("{}", { status: 404 })),
    );
  });
  afterEach(() => {
    rendered?.unmount();
    vi.unstubAllGlobals();
  });

  it("offers another weather, its commands to take back and checkpoints, unreplayed", () => {
    rendered = panels();
    const { container } = rendered;

    expect(container.querySelector('[data-testid="replayed-weather"]')).toBeNull();
    expect(container.querySelector('[data-testid="schedule-fixed"]')).toBeNull();
    expect(container.querySelector('[data-testid="replayed-checkpoints"]')).toBeNull();
    expect(container.querySelector('button[aria-label^="Remove"]')).not.toBeNull();
    expect(said(container, "weather-offers")).toBe("3");
  });

  it("says why the weather, the commands and the checkpoints stay as they are", () => {
    rendered = panels({ replayed: true });
    const { container } = rendered;

    expect(said(container, "replayed-weather")).toMatch(/keeps the weather/);
    expect(said(container, "schedule-fixed")).toMatch(/commands are its own/);
    expect(said(container, "replayed-checkpoints")).toMatch(/fork it there/);
    // And nothing of them changes another run than the one replayed.
    expect(container.querySelector('button[aria-label^="Remove"]')).toBeNull();
    expect(container.querySelector('button[aria-label^="Repeat"]')).toBeNull();
    expect(said(container, "weather-offers")).toBe("0");
  });

  it("says the moment as the replay's timeline does, and a view's as a view's", () => {
    const at = {
      kind: "scenario",
      scenarioId: "box",
      field: CLIMATE_FIELD,
      time: 786_240,
    } as const;

    rendered = panels({ source: at, replayed: true });
    expect(said(rendered.container, "climate-time")).toBe("Day 10, 02:24");
    expect(said(rendered.container, "moment-summary")).toBe("Climate run: loading Day 10, 02:24…");
    rendered.unmount();

    rendered = panels({ source: at });
    expect(said(rendered.container, "climate-time")).toBe("day 9, 2 h 24 min");
  });

  it("makes a fork of levels once it is asked for, and not as a slider moves", () => {
    const onFork = vi.fn();
    const onPutBack = vi.fn();
    rendered = panels({ replayed: true, forkLevels: { asked: {}, onFork, onPutBack } });
    const fork = () =>
      button(rendered?.container as HTMLElement, "Fork from here with these levels");

    expect(said(rendered.container, "fork-levels")).toMatch(/keeps its levels/);
    expect(fork().disabled).toBe(true);
    rendered.unmount();

    rendered = panels({
      replayed: true,
      forkLevels: { asked: { heater: 0.5 }, onFork, onPutBack },
    });
    expect(said(rendered.container, "fork-levels")).toMatch(/Set heater/);
    click(fork());
    expect(onFork).toHaveBeenCalledOnce();
    click(button(rendered.container, "Put them back"));
    expect(onPutBack).toHaveBeenCalledOnce();
  });

  it("goes to one of a stored run's commands by moving its position", () => {
    const onSeek = vi.fn();
    const onSource = vi.fn();
    rendered = panels({ replayed: true, onSeek, onSource });

    const goTo = rendered.container.querySelector<HTMLButtonElement>('button[aria-label^="Go to"]');
    expect(goTo).not.toBeNull();
    click(goTo as HTMLButtonElement);

    expect(onSeek).toHaveBeenCalledWith(60);
    expect(onSource).not.toHaveBeenCalled();
  });
});
