// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";

import { SceneStatus } from "./SceneStatus";
import type { SceneState } from "./scene/sceneLoad";
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

  it("shows a scene on its way", () => {
    const said = status({ status: "loading" });

    expect(said.className).not.toContain("visually-hidden");
    expect(said.textContent).toBe("Loading the scenario climate_box, before day one…");
  });

  it("shows why a scene could not be drawn, as an alert", () => {
    const said = status({ status: "rejected", problems: ["no greenhouse"] });

    expect(said.className).not.toContain("visually-hidden");
    expect(said.getAttribute("role")).toBe("alert");
    expect(said.textContent).toContain("was rejected: no greenhouse");
  });

  it("shows why a scene is not available, as an alert", () => {
    const said = status({ status: "unavailable", reason: "the simulator could not be reached" });

    expect(said.className).not.toContain("visually-hidden");
    expect(said.getAttribute("role")).toBe("alert");
  });
});
