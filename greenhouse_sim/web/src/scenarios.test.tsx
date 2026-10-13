import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ScenarioList } from "./ScenarioList";
import { loadScenarios, openingMoment, parseScenarios, type ScenarioSummary } from "./scenarios";

const DEMO: ScenarioSummary = {
  id: "climate_box",
  name: "Agentic Demo Greenhouse",
  description: "A short walkthrough greenhouse",
  plants: 6,
  duration_days: 15,
  layouts: ["default"],
};
const SIMULATION: ScenarioSummary = {
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

    expect(html).toContain(">Agentic Demo Greenhouse</td>");
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
});
