import { describe, expect, it } from "vitest";

import {
  describeManifest,
  loadRunManifest,
  loadServedVersion,
  parseRunManifest,
  type RunManifest,
  runManifestUrl,
} from "./manifest";

// The reference greenhouse's run, as the simulator serves its manifest.
const SERVED_MANIFEST = {
  scenario_id: "reference_greenhouse",
  schema_version: 1,
  version: "5a7c1ee05a34bf3c",
  random_seed: 42,
  start_date: "2026-03-01",
  duration_days: 120,
  opening_day: 80,
  crop_model: "organ",
  variety: "cherry_tomato",
  airflow: "uniform",
  weather: "default",
  weather_kind: "synthetic",
  cloud_cover_pct: null,
  wind_from_deg: null,
};

const MANIFEST: RunManifest = {
  scenarioId: "reference_greenhouse",
  format: 1,
  version: "5a7c1ee05a34bf3c",
  seed: 42,
  startDate: "2026-03-01",
  days: 120,
  openingDay: 80,
  cropModel: "organ",
  variety: "cherry_tomato",
  airflow: "uniform",
  weather: "default",
  weatherKind: "synthetic",
  cloudCoverPct: null,
  windFromDeg: null,
};

function answering(body: unknown, status = 200): typeof fetch {
  return (async () => new Response(JSON.stringify(body), { status })) as typeof fetch;
}

describe("a run's manifest", () => {
  it("is asked for under the run's weather alone", () => {
    expect(runManifestUrl("climate_box", { time: 600, levels: { fan: 1 } })).toBe(
      "/api/scenarios/climate_box/manifest",
    );
    expect(runManifestUrl("climate_box", { weather: "default@80~90" })).toBe(
      "/api/scenarios/climate_box/manifest?weather=default%4080~90",
    );
  });

  it("is read as served, and checked", async () => {
    expect(parseRunManifest(SERVED_MANIFEST)).toEqual(MANIFEST);
    expect(() => parseRunManifest({ ...SERVED_MANIFEST, random_seed: "42" })).toThrow(
      "the run's manifest is not what the viewer expects",
    );
    expect(await loadRunManifest("/m", answering(SERVED_MANIFEST))).toEqual({
      status: "loaded",
      manifest: MANIFEST,
    });
    expect(await loadRunManifest("/m", answering({ error: "no" }, 404))).toEqual({
      status: "unavailable",
      reason: "the simulator API answered 404",
    });
  });

  it("is said in words, a line for each of its parts", () => {
    expect(describeManifest(MANIFEST)).toEqual({
      scenario: "reference_greenhouse, version 5a7c1ee05a34bf3c, format 1",
      seed: "42",
      season: "from 2026-03-01, 120 days, opening on day 80",
      crop: "cherry_tomato, organ by organ",
      airflow: "uniform, prescribed",
      weather: "its own, synthetic",
    });
    const other = describeManifest({
      ...MANIFEST,
      openingDay: null,
      cropModel: "simple",
      weather: "cold_spring_day",
      cloudCoverPct: 80,
      windFromDeg: 90,
    });
    expect(other.season).toBe("from 2026-03-01, 120 days");
    expect(other.crop).toBe("cherry_tomato, the simple daily model");
    expect(other.weather).toBe("cold_spring_day, synthetic, clouds 80%, wind from 90°");
  });
});

describe("the simulator's version", () => {
  it("is read with its commit, and checked", async () => {
    const body = { simulator: "greenhouse-sim", version: "0.1.0", commit: "c1964e9" };
    expect(await loadServedVersion("/api/version", answering(body))).toEqual({
      status: "loaded",
      served: { version: "0.1.0", commit: "c1964e9" },
    });
    expect(await loadServedVersion("/api/version", answering({ version: "0.1.0" }))).toEqual({
      status: "unavailable",
      reason: "the simulator's version is not what the viewer expects",
    });
  });
});
