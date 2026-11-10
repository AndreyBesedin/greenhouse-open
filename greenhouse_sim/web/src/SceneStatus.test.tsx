// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";

import { SceneStatus } from "./SceneStatus";
import type { SceneState } from "./scene/sceneLoad";
import { SUPPORTED_SCHEMA_VERSION } from "./scene/schemaVersion";
import type { SceneSource } from "./scene/source";
import { type Rendered, render } from "./testing/render";

const SOURCE: SceneSource = { kind: "scenario", scenarioId: "climate_box" };

describe("what the viewer says of the scene it draws", () => {
  let rendered: Rendered | undefined;
  afterEach(() => rendered?.unmount());

  function status(state: SceneState): HTMLElement {
    rendered = render(<SceneStatus source={SOURCE} state={state} />);
    const found = rendered.container.querySelector<HTMLElement>('[data-testid="scene-status"]');
    if (found === null) {
      throw new Error("no status");
    }
    return found;
  }

  it("does not show what is drawn, but announces it politely", () => {
    const said = status({ status: "none" });

    expect(said.className).toContain("visually-hidden");
    expect(said.getAttribute("role")).toBe("status");
    expect(said.textContent).toBe("Showing the scenario climate_box, before day one.");
  });

  it("says how many days its crop has lived as a count, not as the name of a day", () => {
    const loaded = (days: number): SceneState => ({
      status: "loaded",
      snapshot: {
        schema_version: SUPPORTED_SCHEMA_VERSION,
        greenhouse_id: "climate_box",
        simulated_day: days,
        entities: [],
      },
    });

    // Noon on day 87 is drawn 86 days in: "day 86" would name the day before.
    expect(status(loaded(86)).textContent).toBe(
      "Showing the scenario climate_box: climate_box, 86 days in, 0 entities.",
    );
    rendered?.unmount();
    expect(status(loaded(1)).textContent).toContain("climate_box, 1 day in,");
    rendered?.unmount();
    expect(status(loaded(0)).textContent).toBe(
      "Showing the scenario climate_box, before day one: climate_box, 0 days in, 0 entities.",
    );
  });

  it("shows a scene on its way", () => {
    const said = status({ status: "loading" });

    expect(said.className).not.toContain("visually-hidden");
    expect(said.textContent).toBe("Loading the scenario climate_box, before day one…");
  });

  it("shows why a scene could not be drawn, as an alert", () => {
    const said = status({ status: "rejected", problems: ["no greenhouse"] });

    expect(said.className).not.toContain("visually-hidden");
    expect(said.getAttribute("role")).toBe("alert");
    // On the chooser's line, where `Notice`, a paragraph, cannot stand: in --warn by its class.
    expect(said.className).toBe("source-problem");
    expect(said.textContent).toBe("The scenario climate_box was rejected: no greenhouse.");
  });

  it("shows why a scene is not available, as an alert", () => {
    const said = status({ status: "unavailable", reason: "the simulator could not be reached" });

    expect(said.className).not.toContain("visually-hidden");
    expect(said.getAttribute("role")).toBe("alert");
    // On the chooser's line, where `Notice`, a paragraph, cannot stand: in --warn by its class.
    expect(said.className).toBe("source-problem");
    expect(said.textContent).toBe(
      "The scenario climate_box is not available: the simulator could not be reached.",
    );
  });
});
