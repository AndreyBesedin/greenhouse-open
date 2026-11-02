import { describe, expect, it } from "vitest";

import {
  LANDING_PATH,
  newRunAddress,
  newRunScenario,
  pageAt,
  VIEWER_PATH,
  viewerAddress,
} from "./paths";

describe("the viewer's addresses", () => {
  it("shows the landing page at the bare address, with or without its slash", () => {
    expect(pageAt(LANDING_PATH, "")).toBe("landing");
    expect(pageAt("", "")).toBe("landing");
  });

  it("still shows the viewer at an address with a query, as links to it always have", () => {
    expect(pageAt("/", "?scenario=climate_box")).toBe("viewer");
    expect(pageAt("/", "?scene=example")).toBe("viewer");
    expect(pageAt("/", "?plants=lab&day=45")).toBe("viewer");
  });

  it("shows the viewer at its own address and at any other path", () => {
    expect(pageAt(VIEWER_PATH, "")).toBe("viewer");
    expect(pageAt(`${VIEWER_PATH}/`, "")).toBe("viewer");
    expect(pageAt("/anything-else", "")).toBe("viewer");
  });

  it("writes an address that names the scenario, its identifier made safe", () => {
    expect(viewerAddress("climate_box")).toBe("/view?scenario=climate_box");
    expect(viewerAddress("a b&c")).toBe("/view?scenario=a%20b%26c");
  });

  it("asks the landing page for a scenario's new-run form by a fragment, which is still the bare address", () => {
    expect(newRunAddress("my house/1")).toBe("/#run=my%20house%2F1");
    expect(pageAt("/", "")).toBe("landing");
    expect(newRunScenario("#run=my%20house%2F1")).toBe("my house/1");
    expect(newRunScenario("")).toBeNull();
    expect(newRunScenario("#run=")).toBeNull();
    expect(newRunScenario("#elsewhere")).toBeNull();
    expect(newRunScenario("#run=%E0%A4%A")).toBeNull();
  });
});
