// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  keepHouse,
  keepSettings,
  keptFields,
  keptHouse,
  uploadedAddress,
  uploadedHouse,
  uploadedHouseAddress,
  uploadedScenario,
} from "./uploaded";

describe("how an uploaded scenario reaches the builder (P17.11)", () => {
  afterEach(() => {
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  it("is named by the builder's address, and read from it", () => {
    expect(uploadedAddress("shared box")).toBe("/builder#scenario=shared%20box");
    expect(uploadedScenario("#scenario=shared%20box")).toBe("shared box");
  });

  it.each(["", "#", "#scenario=", "#run=shared_box", "#scenario=%E0%A4%A"])(
    "is not asked for by the fragment %j",
    (hash) => {
      expect(uploadedScenario(hash)).toBeNull();
    },
  );

  it("keeps a scenario's run settings as the run step's fields", () => {
    keepSettings("shared_box", {
      start_date: "2026-03-01",
      duration_days: 12,
      random_seed: 3,
      weather: "default",
    });

    expect(keptFields("shared_box")).toEqual({
      start: "2026-03-01",
      days: "12",
      weather: "default",
      seed: "3",
    });
    expect(keptFields("another")).toBeNull();
  });

  it("names an installation's file by another address than a scenario's", () => {
    expect(uploadedHouseAddress("my house")).toBe("/builder#installation=my%20house");
    expect(uploadedHouse("#installation=my%20house")).toBe("my house");
    expect(uploadedScenario("#installation=my%20house")).toBeNull();
    expect(uploadedHouse("#scenario=my%20house")).toBeNull();
    expect(uploadedHouse("#installation=")).toBeNull();
  });

  it("keeps an installation's file for the builder, or says it could not", () => {
    const house = { fileName: "my_greenhouse.json", text: "{}" };

    expect(keepHouse("my_greenhouse", house)).toBe(true);
    expect(keptHouse("my_greenhouse")).toEqual(house);
    expect(keptHouse("another")).toBeNull();

    sessionStorage.setItem("greenhouse.uploaded-house.torn", JSON.stringify({ text: "{}" }));
    expect(keptHouse("torn")).toBeNull();

    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("refused");
    });
    expect(keepHouse("refused", house)).toBe(false);
  });

  it("keeps nothing it cannot read back whole", () => {
    sessionStorage.setItem("greenhouse.uploaded.a", "not json");
    sessionStorage.setItem("greenhouse.uploaded.b", JSON.stringify({ start_date: "2026-03-01" }));

    expect(keptFields("a")).toBeNull();
    expect(keptFields("b")).toBeNull();
  });

  it("opens with a first run's settings when the browser keeps nothing", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("refused");
    });
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("refused");
    });

    expect(() =>
      keepSettings("shared_box", {
        start_date: "2026-03-01",
        duration_days: 12,
        random_seed: 3,
        weather: "default",
      }),
    ).not.toThrow();
    expect(keptFields("shared_box")).toBeNull();
  });
});
