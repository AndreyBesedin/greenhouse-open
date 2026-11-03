import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ScenarioList, scenarioMatches } from "./ScenarioList";
import { loadScenarios, openingMoment, parseScenarios, type ScenarioSummary } from "./scenarios";

// What the simulator sends of a scenario besides: how it grows its crop,
// its own daily commands, its openings and weathers, and the day it opens
// on and the heater a thermostat runs, if any.
const SENT = {
  crop_model: "simple",
  daily: [],
  openings: [],
  weathers: ["default"],
  opening_day: null,
  thermostat: null,
};
const DEMO: ScenarioSummary = {
  ...SENT,
  id: "climate_box",
  name: "Agentic Demo Greenhouse",
  description: "A short walkthrough greenhouse",
  plants: 6,
  duration_days: 15,
  layouts: ["default"],
};
const SIMULATION: ScenarioSummary = {
  ...SENT,
  id: "tomato_compartment",
  name: "Simulation Greenhouse 001",
  description: "Forty plants",
  plants: 40,
  duration_days: 28,
  layouts: ["default", "benches"],
};

function answering(status: number, body: unknown): typeof fetch {
  return async () => new Response(JSON.stringify(body), { status });
}

describe("reading the simulator's scenario list", () => {
  it("accepts a list of scenario summaries", () => {
    expect(parseScenarios([DEMO])).toEqual([DEMO]);
  });

  it.each([
    ["not a list", { scenarios: [DEMO] }],
    ["a summary without a plant count", [{ ...DEMO, plants: undefined }]],
    ["a fractional plant count", [{ ...DEMO, plants: 6.5 }]],
    ["a summary that is not an object", ["climate_box"]],
    ["a summary without its layouts", [{ ...DEMO, layouts: undefined }]],
    ["a layout that is not a name", [{ ...DEMO, layouts: [1] }]],
  ])("refuses %s", (_, body) => {
    expect(() => parseScenarios(body)).toThrow();
  });

  it("loads the scenarios the API returns", async () => {
    expect(await loadScenarios(answering(200, [DEMO]))).toEqual({
      status: "loaded",
      scenarios: [DEMO],
    });
  });

  it("reports an error status as unavailable", async () => {
    expect(await loadScenarios(answering(502, { error: "bad gateway" }))).toEqual({
      status: "unavailable",
      reason: "the simulator API answered 502",
    });
  });

  it("reports an unreachable API as unavailable", async () => {
    const unreachable: typeof fetch = async () => {
      throw new TypeError("fetch failed");
    };

    expect(await loadScenarios(unreachable)).toEqual({
      status: "unavailable",
      reason: "fetch failed",
    });
  });
});

describe("the scenario list", () => {
  it("shows each scenario by name, its identifier on hover, with its plants and length", () => {
    const html = renderToStaticMarkup(
      <ScenarioList state={{ status: "loaded", scenarios: [DEMO] }} />,
    );

    expect(html).toContain('<span class="scenario-name">Agentic Demo Greenhouse</span>');
    expect(html).toContain(
      '<span class="scenario-description">A short walkthrough greenhouse</span>',
    );
    expect(html).toContain('title="climate_box: ');
    expect(html).toContain("<td>6</td><td>15</td>");
  });

  it("offers a picker of layouts for a scenario that has several", () => {
    const html = renderToStaticMarkup(
      <ScenarioList
        state={{ status: "loaded", scenarios: [DEMO, SIMULATION] }}
        shownLayout={{ scenarioId: "tomato_compartment", layout: "benches" }}
        onShow={() => undefined}
      />,
    );

    expect(html).toContain("<th>Layout</th>");
    expect(html).toContain('aria-label="Layout of tomato_compartment"');
    expect(html).not.toContain('aria-label="Layout of climate_box"');
    expect(html).toContain('<option value="benches" selected="">benches</option>');
  });

  it("opens a scenario by a button that says so", () => {
    const html = renderToStaticMarkup(
      <ScenarioList state={{ status: "loaded", scenarios: [DEMO] }} onShow={() => undefined} />,
    );

    expect(html).toContain('aria-label="Open climate_box">Open</button>');
  });

  it("lists the scenarios a filter matches, by name, identifier or description", () => {
    expect(scenarioMatches(DEMO, " walkthrough ")).toBe(true);
    expect(scenarioMatches(DEMO, "CLIMATE_")).toBe(true);
    expect(scenarioMatches(DEMO, "agentic demo")).toBe(true);
    expect(scenarioMatches(DEMO, "benches")).toBe(false);
    const html = renderToStaticMarkup(
      <ScenarioList state={{ status: "loaded", scenarios: [DEMO, SIMULATION] }} filter="forty" />,
    );
    expect(html).toContain("Simulation Greenhouse 001");
    expect(html).not.toContain("Agentic Demo Greenhouse");
  });

  it("offers no layouts where every scenario has one", () => {
    const html = renderToStaticMarkup(
      <ScenarioList state={{ status: "loaded", scenarios: [DEMO] }} onShow={() => undefined} />,
    );

    expect(html).not.toContain("Layout");
  });

  it("says how to start the API when it cannot be reached", () => {
    const html = renderToStaticMarkup(
      <ScenarioList state={{ status: "unavailable", reason: "fetch failed" }} />,
    );

    expect(html).toContain('role="alert"');
    expect(html).toContain("python -m greenhouse_sim.api");
  });
});

describe("a scenario's opening day", () => {
  it("opens the scenario shown from the list at noon on it, its climate drawn", () => {
    const reference = parseScenarios([
      {
        ...SENT,
        id: "reference_greenhouse",
        name: "Reference greenhouse",
        description: "",
        plants: 32,
        duration_days: 120,
        layouts: ["default"],
        opening_day: 80,
      },
    ])[0];

    expect(openingMoment(reference)).toEqual({ field: "climate", time: 80.5 * 86_400 });
    expect(openingMoment({ ...reference, opening_day: null } as never)).toBeNull();
    expect(openingMoment(undefined)).toBeNull();
    expect(() => parseScenarios([{ ...reference, opening_day: "eighty" }])).toThrow(
      "scenario 0 is not a scenario summary",
    );
  });

  it("says which heater a thermostat runs, if one does", () => {
    const base = { ...SENT, id: "a", name: "A", description: "", plants: 1, duration_days: 1 };
    const [heated] = parseScenarios([{ ...base, layouts: ["default"], thermostat: "heater" }]);

    expect(heated?.thermostat).toBe("heater");
    expect(() => parseScenarios([{ ...base, layouts: ["default"], thermostat: 1 }])).toThrow(
      "scenario 0 is not a scenario summary",
    );
  });
});
