import { readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import { describe, expect, it } from "vitest";

import {
  describeProbes,
  gzippedJson,
  loadReferenceQa,
  parseReferenceQa,
  QA_REFERENCE_VIEWS,
  qaReferenceView,
  REFERENCE_VIEWS,
  referenceScale,
} from "./referenceViews";

const ZIPPED = readFileSync(
  new URL("../../public/scenes/qa-reference-greenhouse.json.gz", import.meta.url),
);
const BODY: unknown = JSON.parse(gunzipSync(ZIPPED).toString("utf8"));
const QA = parseReferenceQa(BODY);

describe("the reference greenhouse's golden views", () => {
  it("are the ones the design names, the noon's by default", () => {
    expect(qaReferenceView("")).toBe("noon");
    expect(qaReferenceView("?view=fans-off")).toBe("fans-off");
    expect(qaReferenceView("?view=midnight")).toBeNull();
    expect(Object.keys(REFERENCE_VIEWS)).toEqual([...QA_REFERENCE_VIEWS]);
  });

  it("draw moments of the opening day, and a young crop's", () => {
    expect(QA.moments.noon.cropDay).toBe(86);
    expect(QA.moments.young.cropDay).toBe(21);
    expect(Object.keys(QA.crops).sort()).toEqual(["21", "86"]);
    // The house is kept without its crop, which the crop's day gives.
    expect(QA.moments.noon.house.entities.some((entity) => "organ_id" in entity.properties)).toBe(
      false,
    );
    // The noon's sun high in the south, its path through the day.
    expect(QA.moments.noon.weather.sun.elevation_deg).toBeCloseTo(59.19, 1);
    expect(QA.sunPath.sun.length).toBeGreaterThan(100);
  });

  it("draw the views compared on one scale", () => {
    const fansOn = referenceScale(QA, REFERENCE_VIEWS["fans-on"]);
    const fansOff = referenceScale(QA, REFERENCE_VIEWS["fans-off"]);
    expect(fansOn).toEqual(fansOff);
    expect(fansOn).toMatchObject({ quantity: "speed", range: { min: 0 } });
    const open = referenceScale(QA, REFERENCE_VIEWS["vents-open"]);
    expect(open).toEqual(referenceScale(QA, REFERENCE_VIEWS["vents-closed"]));
    expect(open?.quantity).toBe("temperature");
    // Shut, the house is warmer than the open house's warmest air.
    expect(open?.range.max).toBeGreaterThan(40);
    expect(referenceScale(QA, REFERENCE_VIEWS["radiation-slice"])?.quantity).toBe("par");
    expect(referenceScale(QA, REFERENCE_VIEWS.noon)).toBeNull();
  });

  it("say their state probes", () => {
    expect(describeProbes(QA.moments.noon.probes)).toBe(
      "house air 28.14 °C, sun 59.19° up, jet 1.39 m/s, vents exchange 1.08 m³/s, " +
        "10373 leaves, 741 fruits, 1 red",
    );
    expect(describeProbes({})).toBe("");
  });

  it("read the file zipped, or as a server has unzipped it", async () => {
    expect(await gzippedJson(new Response(ZIPPED))).toEqual(BODY);
    expect(await gzippedJson(new Response(JSON.stringify({ a: 1 })))).toEqual({ a: 1 });
    const missing = await loadReferenceQa(
      "/qa",
      (async () => new Response("", { status: 404 })) as typeof fetch,
    );
    expect(missing).toEqual({ status: "missing", reason: "the file answered 404" });
  });

  it("are checked rather than trusted", () => {
    expect(() => parseReferenceQa(null)).toThrow("not what the viewer expects");
    expect(() => parseReferenceQa({ moments: {}, crops: {} })).toThrow("has no dawn");
    const body = BODY as { crops: Record<string, unknown> };
    expect(() => parseReferenceQa({ ...body, crops: { "86": body.crops["86"] } })).toThrow(
      "no crop on day 21",
    );
  });
});
