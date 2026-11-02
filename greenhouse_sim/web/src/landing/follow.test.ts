import { describe, expect, it } from "vitest";

import { followAddress } from "./follow";

describe("the address that follows a scenario's run", () => {
  it("names the scenario, and follows its climate", () => {
    expect(followAddress("climate_box")).toBe("/view?scenario=climate_box&field=climate&follow=1");
  });

  it("follows a run in the layout it has, when that is not its scenario's own", () => {
    expect(followAddress("climate_box", "default")).toBe(followAddress("climate_box"));
    expect(followAddress("climate_box", "default~heater:-1:0.5")).toBe(
      "/view?scenario=climate_box&layout=default~heater:-1:0.5&field=climate&follow=1",
    );
  });
});
