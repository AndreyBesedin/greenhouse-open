// @vitest-environment jsdom
import { act } from "react";
import { describe, expect, it } from "vitest";

import { back } from "../testing/history";
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

  it("makes another scene a new page, and a change within one a change of the page", () => {
    openAt("?scenario=climate_box");
    const hook = renderHook(useSource, undefined);
    const pages = history.length;

    act(() =>
      hook.current[1]((current) =>
        current.kind === "scenario" ? { ...current, field: "climate", time: 600 } : current,
      ),
    );
    expect(history.length).toBe(pages);
    act(() => hook.current[1]({ kind: "scenario", scenarioId: "climate_box", layout: "benches" }));
    expect(history.length).toBe(pages + 1);
    act(() => hook.current[1]({ kind: "example" }));
    expect(history.length).toBe(pages + 2);
    expect(location.search).toBe("?scene=example");
    hook.unmount();
  });

  it("returns on Back to the view before, as its address held it", async () => {
    openAt("?scenario=climate_box&field=climate&t=600");
    const hook = renderHook(useSource, undefined);
    act(() => hook.current[1]({ kind: "example" }));

    await back();

    expect(location.search).toBe("?scenario=climate_box&field=climate&t=600");
    expect(hook.current[0]).toMatchObject({
      kind: "scenario",
      scenarioId: "climate_box",
      time: 600,
    });
    // Back where it was, a change replaces that page again.
    const pages = history.length;
    act(() => hook.current[1]({ kind: "scenario", scenarioId: "climate_box" }));
    expect(history.length).toBe(pages);
    expect(location.search).toBe("?scenario=climate_box");
    hook.unmount();
  });
});
