// @vitest-environment jsdom
import { act } from "react";
import { describe, expect, it } from "vitest";
import { useSource } from "../scene/useSource";
import { renderHook } from "../testing/renderHook";
import { qaModeFrom, useQaMode, withQaMode } from "./mode";

function openAt(search: string): void {
  history.replaceState(null, "", `/${search}`);
}

describe("QA mode, in the address", () => {
  it("is on only with qa=1", () => {
    expect(qaModeFrom("?scenario=climate_box&qa=1")).toBe(true);
    expect(qaModeFrom("?qa=1")).toBe(true);
    expect(qaModeFrom("?scenario=climate_box")).toBe(false);
    expect(qaModeFrom("?qa=0")).toBe(false);
    expect(qaModeFrom("")).toBe(false);
  });

  it("is written at the address's end, the rest as it was", () => {
    expect(withQaMode("?scenario=a&probes=1:2:3,4:5:6", true)).toBe(
      "?scenario=a&probes=1:2:3,4:5:6&qa=1",
    );
    expect(withQaMode("", true)).toBe("?qa=1");
    expect(withQaMode("?qa=1&scenario=a", true)).toBe("?scenario=a&qa=1");
    expect(withQaMode("?scenario=a&qa=1", false)).toBe("?scenario=a");
    expect(withQaMode("?qa=1", false)).toBe("");
  });

  it("is read once, and kept in the address as it changes", () => {
    openAt("?scenario=climate_box&qa=1");
    const hook = renderHook(useQaMode, undefined);
    expect(hook.current[0]).toBe(true);

    act(() => hook.current[1](false));
    expect(location.search).toBe("?scenario=climate_box");
    act(() => hook.current[1](true));
    expect(location.search).toBe("?scenario=climate_box&qa=1");
  });

  it("stays in the address as the scene's source changes", () => {
    openAt("?scenario=climate_box&qa=1");
    const hook = renderHook(useSource, undefined);

    act(() => hook.current[1]({ kind: "scenario", scenarioId: "gh_001" }));
    expect(location.search).toBe("?scenario=gh_001&qa=1");
    act(() => hook.current[1]({ kind: "reference" }));
    expect(location.search).toBe("?qa=1");
  });
});
