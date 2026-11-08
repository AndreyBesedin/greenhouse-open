// @vitest-environment jsdom
import type { ComponentProps } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { CLIMATE_FIELD } from "./fields/source";
import { WHAT_A_FORK_DOES } from "./replay/useForkQuestion";
import { ScenarioPanels } from "./ScenarioPanels";
import type { SceneSnapshot } from "./scene/generated/snapshotTypes";
import { button, click, enter, type Rendered, render, said } from "./testing/render";

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
const EQUIPPED = {
  greenhouse_id: "box",
  entities: [
    ...["heater", "fan"].map((id) => ({
      entity_id: id,
      kind: "EQUIPMENT",
      properties: { actuator_id: id, level: 0, does: "heats", heats_w: 10_000 },
    })),
    ...["roof_vent", "door"].map((id) => ({
      entity_id: id,
      kind: "OPENING",
      properties: { opening_id: id, open_fraction: 0, aperture_m2: 0 },
    })),
  ],
} as unknown as SceneSnapshot;

function panelsElement(more: Partial<ComponentProps<typeof ScenarioPanels>> = {}) {
  return (
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
    />
  );
}

function panels(more: Partial<ComponentProps<typeof ScenarioPanels>> = {}) {
  return render(panelsElement(more));
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
    expect(said(rendered.container, "climate-time")).toBe("day 10, 2 h 24 min");
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
    expect(onFork).not.toHaveBeenCalled();
    expect(said(rendered.container, "fork-question")).toContain(WHAT_A_FORK_DOES);
    click(button(rendered.container, "Make the fork"));
    expect(onFork).toHaveBeenCalledOnce();
    click(button(rendered.container, "Put them back"));
    expect(onPutBack).toHaveBeenCalledOnce();
  });

  it("gives up the question of a fork of levels if the levels change, or are cancelled", () => {
    const onFork = vi.fn();
    const forkLevels = (asked: Record<string, number>) => ({
      replayed: true,
      forkLevels: { asked, onFork, onPutBack: vi.fn() },
    });
    rendered = panels(forkLevels({ heater: 0.5 }));
    const { container } = rendered;
    const fork = button(container, "Fork from here with these levels");
    const question = () => container.querySelector('[data-testid="fork-question"]');

    click(fork);
    click(button(container, "Cancel"));
    expect(question()).toBeNull();
    expect(document.activeElement).toBe(fork);

    click(fork);
    expect(question()).not.toBeNull();
    rendered.rerender(panelsElement(forkLevels({ heater: 0.75 })));
    expect(question()).toBeNull();
    expect(onFork).not.toHaveBeenCalled();
  });

  it("names the moment a fork of levels takes when the transport reads another", () => {
    const onFork = vi.fn();
    rendered = panels({
      replayed: true,
      forkLevels: { asked: { heater: 0.5 }, onFork, onPutBack: vi.fn(), from: "Day 1, 24:00" },
    });

    click(button(rendered.container, "Fork from Day 1, 24:00 with these levels"));
    click(button(rendered.container, "Make the fork"));
    expect(onFork).toHaveBeenCalledOnce();
  });

  it("says why no fork of levels can be made at a run's end, and offers none", () => {
    const onFork = vi.fn();
    rendered = panels({
      replayed: true,
      forkLevels: {
        asked: { heater: 0.5 },
        onFork,
        onPutBack: vi.fn(),
        noFork: "The run ends here: go back to a moment to fork from.",
      },
    });

    expect(said(rendered.container, "fork-levels")).toMatch(/The run ends here/);
    const fork = button(rendered.container, "Fork from here with these levels");
    expect(fork.disabled).toBe(true);
    // What was set can still be put back.
    expect(button(rendered.container, "Put them back").disabled).toBe(false);
  });

  it("reads a level set in a replay beside what the scene drawn has, as it will not take it up", () => {
    const set = { heater: 1, roof_vent: 0.6 };
    rendered = panels({
      replayed: true,
      snapshot: EQUIPPED,
      steering: { at: 0, asked: set, onLevels: vi.fn() },
      forkLevels: { asked: set, onFork: vi.fn(), onPutBack: vi.fn() },
    });

    expect(said(rendered.container, "equipment-heater")).toBe("off, set to 100%");
    expect(said(rendered.container, "equipment-fan")).toBe("off");
    expect(said(rendered.container, "opening-roof_vent")).toBe("0%, 0 m², set to 60%");
    expect(said(rendered.container, "opening-door")).toBe("0%, 0 m²");
    rendered.unmount();

    // Out of a replay, the scene catches up with what was asked.
    rendered = panels({
      snapshot: EQUIPPED,
      steering: { at: 0, asked: set, onLevels: vi.fn() },
    });
    expect(said(rendered.container, "equipment-heater")).toBe("off");
  });

  it("steers a running epoch with what is set in them, and offers no fork of it", () => {
    const set = { heater: 1 };
    const onTargets = vi.fn();
    rendered = panels({
      replayed: true,
      steersReplayed: true,
      snapshot: EQUIPPED,
      setpoints: { actuatorId: "heater", setpointC: 18, dayC: 18, nightC: 16, runs: true },
      onTargets,
      steering: { at: 0, asked: set, onLevels: vi.fn() },
    });
    const { container } = rendered;

    expect(container.querySelector('[data-testid="fork-levels"]')).toBeNull();
    // The replay reaches the moment the level takes only later, if it does.
    expect(said(container, "equipment-heater")).toBe("off, set to 100%");
    const day = container.querySelector<HTMLInputElement>('input[type="number"]');
    enter(day as HTMLInputElement, "24");
    click(button(container, "Set from the run's next minute"));
    expect(container.querySelector('[data-testid="fork-question"]')).toBeNull();
    expect(onTargets).toHaveBeenCalledWith({ heating_day: 24 });
  });

  it("names the levels set as the panels do, not by their identifiers", () => {
    rendered = panels({
      replayed: true,
      forkLevels: { asked: { roof_vent_1: 0.5, fan_left: 1 }, onFork: vi.fn(), onPutBack: vi.fn() },
    });
    expect(said(rendered.container, "fork-levels")).toContain(
      "Set roof vent 1, fan left: not yet this run's or a fork's.",
    );
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

  it("counts a stored run's schedule as its timeline does, from day 1", () => {
    const fan = { actuatorId: "fan", level: 1, timeS: 3_398_400 };
    const at = {
      kind: "scenario" as const,
      scenarioId: "box",
      field: CLIMATE_FIELD,
      time: 3_369_600,
      schedule: [fan],
    };

    rendered = panels({ source: at, days: 120, replayed: true });
    expect(said(rendered.container, "schedule-summary")).toBe(
      "Schedule: 1 command. Next at Day 40, 08:00: fan 100%.",
    );
    const goTo = rendered.container.querySelector('button[aria-label^="Go to"]');
    expect(goTo?.textContent).toBe("Day 40, 08:00");
    expect(goTo?.getAttribute("aria-label")).toBe("Go to fan 100% at Day 40, 08:00");
    rendered.unmount();

    // A view keeps its own way of saying a moment.
    rendered = panels({ source: at, days: 120 });
    expect(said(rendered.container, "schedule-summary")).toBe(
      "Schedule: 1 command. Next at day 40, 8 h 00 min: fan 100%.",
    );
  });
});
