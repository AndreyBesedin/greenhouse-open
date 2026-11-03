// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ScenarioSource } from "../scene/edits";
import type { SetSource } from "../scene/useSource";
import { type Rendered, render } from "../testing/render";
import { useAbsentClimate } from "./useAbsentClimate";

const FOLLOWED: ScenarioSource = {
  kind: "scenario",
  scenarioId: "built_house",
  field: "climate",
  follow: true,
  time: 3600,
};

/** The simulator, which lists these fields, or answers `status` if given. */
function listing(fields: string[], status = 200) {
  const fetchFn = vi.fn(
    async () => new Response(JSON.stringify({ fields, configured: "uniform" }), { status }),
  );
  vi.stubGlobal("fetch", fetchFn);
  return fetchFn;
}

describe("a view that asks for a climate its scenario has not", () => {
  let rendered: Rendered | undefined;
  afterEach(() => {
    rendered?.unmount();
    vi.unstubAllGlobals();
  });

  function Probe({
    source,
    replayed,
    onSource,
  }: {
    source: ScenarioSource;
    replayed: boolean;
    onSource: (change: SetSource) => void;
  }) {
    useAbsentClimate({ source, replayed, onSource });
    return null;
  }

  function shown(source: ScenarioSource, replayed = false) {
    const onSource = vi.fn<(change: SetSource) => void>();
    rendered = render(<Probe source={source} replayed={replayed} onSource={onSource} />);
    return onSource;
  }

  const settled = () => new Promise((resolve) => setTimeout(resolve, 0));

  it("draws no field when it follows a run, keeping the rest of the view", async () => {
    listing(["uniform", "shear"]);

    const onSource = shown(FOLLOWED);

    await vi.waitFor(() => expect(onSource).toHaveBeenCalledOnce());
    const change = onSource.mock.calls[0]?.[0];
    expect(typeof change === "function" ? change(FOLLOWED) : change).toEqual({
      kind: "scenario",
      scenarioId: "built_house",
      follow: true,
      time: 3600,
    });
  });

  it("draws no field when it replays a stored run", async () => {
    listing(["uniform", "shear"]);
    const { follow: _, ...replayedSource } = FOLLOWED;

    const onSource = shown(replayedSource, true);

    await vi.waitFor(() => expect(onSource).toHaveBeenCalledOnce());
  });

  it("keeps the climate of a scenario that has one", async () => {
    const asked = listing(["uniform", "climate", "shear"]);

    const onSource = shown(FOLLOWED);

    await vi.waitFor(() => expect(asked).toHaveBeenCalled());
    await settled();
    expect(onSource).not.toHaveBeenCalled();
  });

  it("keeps the climate while the fields cannot be listed", async () => {
    const asked = listing([], 500);

    const onSource = shown(FOLLOWED);

    await vi.waitFor(() => expect(asked).toHaveBeenCalled());
    await settled();
    expect(onSource).not.toHaveBeenCalled();
  });

  it("asks nothing of a view looked at, whose address says what it wants", async () => {
    const asked = listing(["uniform"]);
    const { follow: _, ...lookedAt } = FOLLOWED;

    const onSource = shown(lookedAt);
    await settled();

    expect(asked).not.toHaveBeenCalled();
    expect(onSource).not.toHaveBeenCalled();
  });

  it("leaves another field the view has come to in the meantime", async () => {
    listing(["uniform", "shear"]);

    const onSource = shown(FOLLOWED);

    await vi.waitFor(() => expect(onSource).toHaveBeenCalledOnce());
    const change = onSource.mock.calls[0]?.[0];
    const shear: ScenarioSource = { ...FOLLOWED, field: "shear" };
    expect(typeof change === "function" ? change(shear) : change).toBe(shear);
  });
});
