// @vitest-environment jsdom
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DAY_S } from "../clock";
import { type Rendered, render, said } from "../testing/render";
import { AreaCrop, AreaCropPanel, describeAreaCrop, written } from "./AreaCropPanel";
import { areaCropUrl, loadAreaCrop, parseAreaCrop } from "./areaCrop";

const LAI = { key: "lai", name: "Leaf area index", unit: "m² m⁻²" };
const FRUIT = { key: "fruit_g_m2", name: "Fruit dry weight", unit: "g m⁻²" };
// Two rows of Reduced-State TOMGRO, the first a third of the house's floor,
// through the run's first two days.
const BODY = {
  time_s: 2.5 * DAY_S,
  model: "reduced_tomgro",
  model_name: "Reduced-State TOMGRO",
  basis: "floor",
  quantities: [LAI, FRUIT],
  days: [0, 1, 2],
  scopes: [
    {
      scope_id: "row_1",
      area_m2: 10,
      values: { lai: [0.014, 0.2, 0.4], fruit_g_m2: [0, 0, 0] },
    },
    {
      scope_id: "row_2",
      area_m2: 20,
      values: { lai: [0.014, 0.5, 1.0], fruit_g_m2: [0, 0, 0] },
    },
  ],
  house: { lai: [0.014, 0.4, 0.8], fruit_g_m2: [0, 0, 0] },
};
const RUN = { scenarioId: "tomgro_house", levels: { heater: 1 }, time: 2.5 * DAY_S };

function loaded(body: unknown = BODY) {
  return { status: "loaded" as const, course: parseAreaCrop(body) };
}

describe("a crop grown by area's course", () => {
  it("is asked for as its crop is, at the start of the moment's day", () => {
    expect(areaCropUrl(RUN)).toBe("/api/scenarios/tomgro_house/area_crop?set=heater:1&t=172800");
    // Every moment of a day asks for the same course: playing within it asks
    // for nothing new.
    expect(areaCropUrl({ ...RUN, time: 2 * DAY_S + 1 })).toBe(areaCropUrl(RUN));
    expect(areaCropUrl({ ...RUN, time: 3 * DAY_S - 1 })).toBe(areaCropUrl(RUN));
    expect(areaCropUrl({ scenarioId: "tomgro_house", time: DAY_S / 2 })).toBe(
      "/api/scenarios/tomgro_house/area_crop",
    );
  });

  it("is read with the house's and the rows' least and most on each day", () => {
    const { course } = loaded();

    expect(course).toMatchObject({
      model: "reduced_tomgro",
      modelName: "Reduced-State TOMGRO",
      basis: "floor",
      days: [0, 1, 2],
    });
    expect(course.rows).toBe(2);
    expect(course.quantities[0]).toEqual({
      ...LAI,
      house: [0.014, 0.4, 0.8],
      least: [0.014, 0.2, 0.4],
      most: [0.014, 0.5, 1.0],
    });
  });

  it("is refused when a row, or the house, has not a value on each day", () => {
    const short = structuredClone(BODY);
    short.scopes[1] = { scope_id: "row_2", area_m2: 20, values: { lai: [0.014], fruit_g_m2: [] } };
    const houseless = { ...BODY, house: { lai: [0.014, 0.4, 0.8] } };
    const rowless = { ...BODY, scopes: [] };
    const unmodelled = { ...BODY, model: undefined };

    for (const body of [short, houseless, rowless, unmodelled]) {
      expect(() => parseAreaCrop(body)).toThrow("the crop's course is not what the viewer expects");
    }
  });

  it("is unavailable when the simulator refuses it, saying so", async () => {
    const refused = (async () => new Response("{}", { status: 404 })) as typeof fetch;
    const answered = (async () => Response.json(BODY)) as typeof fetch;

    expect(await loadAreaCrop("/api/scenarios/climate_box/area_crop", refused)).toEqual({
      status: "unavailable",
      reason: "the simulator API answered 404",
    });
    expect((await loadAreaCrop("/x", answered)).status).toBe("loaded");
  });
});

describe("the crop by area panel", () => {
  it("charts each quantity: the house's line over its rows' least to most", () => {
    const html = renderToStaticMarkup(<AreaCrop state={loaded()} />);
    const page = new DOMParser().parseFromString(html, "text/html");
    const charts = [...page.querySelectorAll('svg[role="img"]')];

    expect(charts).toHaveLength(2);
    for (const chart of charts) {
      expect(chart.querySelectorAll("polygon.crop-area-band")).toHaveLength(1);
      expect(chart.querySelectorAll("polyline.crop-area-house")).toHaveLength(1);
    }
    expect(charts[0]?.getAttribute("aria-label")).toBe(
      "The house's leaf area index after each day, in m² m⁻², its rows' least to most behind it",
    );
    // The band runs along the rows' least and back along their most, the
    // house's line between: the most at the chart's head on the last day.
    const band = charts[0]?.querySelector("polygon")?.getAttribute("points")?.split(" ");
    expect(band).toEqual([
      "0.0,28.0",
      "120.0,22.7",
      "240.0,17.0",
      "240.0,0.0",
      "120.0,14.2",
      "0.0,28.0",
    ]);
    expect(charts[0]?.querySelector("polyline")?.getAttribute("points")).toBe(
      "0.0,28.0 120.0,17.0 240.0,5.7",
    );
  });

  it("says each quantity at the moment shown, and that its values are the model's predictions", () => {
    const html = renderToStaticMarkup(<AreaCrop state={loaded()} />);

    expect(html).toContain("Leaf area index 0.800 m² m⁻², rows 0.400 to 1.00");
    expect(html).toContain("Fruit dry weight 0.00 g m⁻², rows alike");
    expect(html).toContain(
      "After 2 days, by Reduced-State TOMGRO: the model&#x27;s predictions, per m² of floor unless a unit " +
        "says otherwise. Each line is the house&#x27;s, its 2 rows weighted by their areas; " +
        "behind it, the rows&#x27; least to most.",
    );
    expect(describeAreaCrop(loaded())).toBe(
      "Crop by area after 2 days: leaf area index 0.800 m² m⁻²",
    );
  });

  it("says its first day's values without charts, the crop as its model plants it", () => {
    const planted = {
      ...BODY,
      time_s: 0,
      days: [0],
      scopes: BODY.scopes.map((scope) => ({
        ...scope,
        values: { lai: [0.014], fruit_g_m2: [0] },
      })),
      house: { lai: [0.014], fruit_g_m2: [0] },
    };
    const html = renderToStaticMarkup(<AreaCrop state={loaded(planted)} />);

    expect(html).not.toContain("<svg");
    expect(html).toContain("As planted, no day lived yet");
    expect(html).toContain("Leaf area index 0.0140 m² m⁻², rows alike");
  });

  it("says when it is on its way, or cannot be read", () => {
    expect(renderToStaticMarkup(<AreaCrop state={{ status: "loading" }} />)).toContain(
      "Growing the crop&#x27;s days…",
    );
    expect(
      renderToStaticMarkup(<AreaCrop state={{ status: "unavailable", reason: "it broke" }} />),
    ).toContain("The crop&#x27;s days cannot be read: it broke.");
    expect(describeAreaCrop({ status: "none" })).toBe("Crop by area");
    expect(describeAreaCrop({ status: "loading" })).toBe("Crop by area: growing…");
    expect(describeAreaCrop({ status: "unavailable", reason: "x" })).toBe(
      "Crop by area: cannot be read",
    );
  });

  it("writes a value to three significant digits, and in whole units from a hundred", () => {
    expect([0.0787, 2.8, 16.89, 168.44, 44640.8, 0].map(written)).toEqual([
      "0.0787",
      "2.80",
      "16.9",
      "168",
      "44641",
      "0.00",
    ]);
  });
});

describe("the crop by area panel, opened", () => {
  let rendered: Rendered | undefined;
  afterEach(() => {
    rendered?.unmount();
    vi.unstubAllGlobals();
  });

  it("asks for nothing while folded, and for the moment's day's course once opened", async () => {
    const asked: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        asked.push(String(input));
        return Response.json(BODY);
      }),
    );
    const folded = { open: false, onToggle: vi.fn() };
    rendered = render(<AreaCropPanel run={RUN} fold={folded} />);
    expect(asked).toEqual([]);
    expect(rendered.container.querySelector("summary")?.textContent).toBe("Crop by area");

    const opened = { ...folded, open: true };
    rendered.rerender(<AreaCropPanel run={RUN} fold={opened} />);
    await vi.waitFor(() =>
      expect(said(rendered?.container ?? document, "area-crop-summary")).toBe(
        "Crop by area after 2 days: leaf area index 0.800 m² m⁻²",
      ),
    );
    expect(asked).toEqual(["/api/scenarios/tomgro_house/area_crop?set=heater:1&t=172800"]);
    // A later moment of the same day asks for nothing more.
    rendered.rerender(<AreaCropPanel run={{ ...RUN, time: 2.9 * DAY_S }} fold={opened} />);
    expect(asked).toHaveLength(1);
  });
});
