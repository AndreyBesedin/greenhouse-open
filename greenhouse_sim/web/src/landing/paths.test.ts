import { describe, expect, it } from "vitest";

import { followAddress, LANDING_PATH, pageAt, VIEWER_PATH, viewerAddress } from "./paths";

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
    expect(followAddress("climate_box")).toBe("/view?scenario=climate_box&field=climate&follow=1");
  });
});
