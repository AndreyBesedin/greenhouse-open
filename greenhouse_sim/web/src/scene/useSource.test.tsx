// @vitest-environment jsdom
import { act } from "react";
import { describe, expect, it } from "vitest";

import { renderHook } from "../testing/renderHook";
import { useSource } from "./useSource";

function openAt(search: string): void {
  history.replaceState(null, "", `/${search}`);
}

describe("the scene's source, kept in the address", () => {
  it("is read from the address the page was opened at", () => {
    openAt("?scenario=climate_box&field=climate&t=600");
    const hook = renderHook(useSource, undefined);

    const [source] = hook.current;
    expect(source).toMatchObject({ kind: "scenario", scenarioId: "climate_box", time: 600 });
  });

  it("leaves that address as it was until the first change", () => {
    openAt("?scenario=climate_box&unknown=1");
    renderHook(useSource, undefined);

    expect(location.search).toBe("?scenario=climate_box&unknown=1");
  });

  it("writes the address with every change, made outright or from the current source", () => {
    openAt("?scenario=climate_box");
    const hook = renderHook(useSource, undefined);

    const [, setSource] = hook.current;
    act(() => setSource({ kind: "scenario", scenarioId: "gh_001" }));
    expect(location.search).toBe("?scenario=gh_001");
    act(() =>
      setSource((current) =>
        current.kind === "scenario" ? { ...current, layout: "benches" } : current,
      ),
    );

    expect(location.search).toBe("?scenario=gh_001&layout=benches");
    expect(hook.current[0]).toEqual({ kind: "scenario", scenarioId: "gh_001", layout: "benches" });
    expect(hook.current[1]).toBe(setSource);
  });
});
