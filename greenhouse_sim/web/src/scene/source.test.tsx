import { readFileSync } from "node:fs";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { SceneStatus } from "../SceneStatus";
import { SNAPSHOT_SCHEMA } from "./generated/snapshotSchema";
import type { SceneSnapshot } from "./generated/snapshotTypes";
import { placement } from "./placement";
import { RENDERERS } from "./renderers";
import { loadScene, type SceneSource, searchFor, sourceFromSearch } from "./source";

const EXAMPLE_TEXT = readFileSync(
  new URL("../../public/scenes/example.json", import.meta.url),
  "utf8",
);
const EXAMPLE: SceneSnapshot = JSON.parse(EXAMPLE_TEXT);

function answering(status: number, body: string): typeof fetch {
  return async () => new Response(body, { status });
}

describe("choosing a scene in the address bar", () => {
  it.each<[string, SceneSource]>([
    ["", { kind: "reference" }],
    ["?scene=example", { kind: "example" }],
    ["?scene=fixtures", { kind: "fixtures" }],
    [
      "?plants=lab",
      { kind: "plants", day: 0, seed: 1, environment: "reference", versus: null, actions: [] },
    ],
    [
      "?plants=lab&day=12",
      { kind: "plants", day: 12, seed: 1, environment: "reference", versus: null, actions: [] },
    ],
    [
      "?plants=lab&day=12&seed=7",
      { kind: "plants", day: 12, seed: 7, environment: "reference", versus: null, actions: [] },
    ],
    [
      "?plants=lab&seed=0",
      { kind: "plants", day: 0, seed: 0, environment: "reference", versus: null, actions: [] },
    ],
    [
      "?plants=lab&day=31&act=30%3Ap01%3Aremove_leaf%3Ap01_n02_leaf&act=31%3Ap01%3Alower_stem%3A1",
      {
        kind: "plants",
        day: 31,
        seed: 1,
        environment: "reference",
        versus: null,
        actions: [
          { day: 30, plantId: "p01", kind: "remove_leaf", target: "p01_n02_leaf" },
          { day: 31, plantId: "p01", kind: "lower_stem", target: "1" },
        ],
      },
    ],
    [
      "?plants=lab&environment=cool_dim&versus=warm_bright",
      {
        kind: "plants",
        day: 0,
        seed: 1,
        environment: "cool_dim",
        versus: "warm_bright",
        actions: [],
      },
    ],
    ["?scenario=gh_demo", { kind: "scenario", scenarioId: "gh_demo" }],
    [
      "?scenario=gh_001&layout=benches",
      { kind: "scenario", scenarioId: "gh_001", layout: "benches" },
    ],
    ["?scenario=gh_001&field=shear", { kind: "scenario", scenarioId: "gh_001", field: "shear" }],
    [
      "?scenario=gh_001&field=shear&fieldView=slice&slice=temperature:z:1.75",
      {
        kind: "scenario",
        scenarioId: "gh_001",
        field: "shear",
        fieldView: "slice",
        slice: { quantity: "temperature", axis: "z", position: 1.75 },
      },
    ],
    [
      "?scenario=gh_001&open=door_1:1&field=vortex&cfd=boundaries",
      {
        kind: "scenario",
        scenarioId: "gh_001",
        openings: { door_1: 1 },
        field: "vortex",
        cfdBoundaries: true,
      },
    ],
  ])("%s", (search, source) => {
    expect(sourceFromSearch(search)).toEqual(source);
    expect(searchFor(source)).toBe(search);
  });
});

describe("loading a scene", () => {
  it("loads nothing for the reference scene", async () => {
    expect(await loadScene({ kind: "reference" })).toEqual({ status: "none" });
  });

  it("draws a scene that passes the check", async () => {
    const state = await loadScene({ kind: "example" }, answering(200, EXAMPLE_TEXT));

    expect(state).toEqual({ status: "loaded", snapshot: EXAMPLE });
  });

  it("rejects a scene that fails the check, saying why", async () => {
    const broken = { ...EXAMPLE, entities: [{ ...EXAMPLE.entities[0], kind: "TREE" }] };

    const state = await loadScene({ kind: "example" }, answering(200, JSON.stringify(broken)));

    expect(state).toEqual({
      status: "rejected",
      problems: ["/entities/0/kind must be equal to one of the allowed values"],
    });
  });

  it("reports a scenario the API does not know, with the API's reason", async () => {
    const state = await loadScene(
      { kind: "scenario", scenarioId: "nope" },
      answering(404, '{"error": "no scenario"}'),
    );

    expect(state).toEqual({
      status: "unavailable",
      reason: "/api/scenarios/nope/scene answered 404: no scenario",
    });
  });

  it("asks the simulator for a scenario's greenhouse changed and opened", async () => {
    const asked: string[] = [];
    const recording: typeof fetch = async (url) => {
      asked.push(String(url));
      return new Response("{}", { status: 500 });
    };
    const source = sourceFromSearch("?scenario=gh_demo&envelope=spans:3,length:12&open=door_1:1");

    await loadScene(source, recording);

    expect(searchFor(source)).toBe("?scenario=gh_demo&envelope=length:12,spans:3&open=door_1:1");
    expect(asked).toEqual([
      "/api/scenarios/gh_demo/scene?envelope=length:12,spans:3&open=door_1:1",
    ]);
  });
});

describe("drawing a checked scene", () => {
  it("places an entity where the snapshot says, in Three.js's quaternion order", () => {
    const entity = EXAMPLE.entities.find((candidate) => candidate.kind === "PLANT");
    if (entity === undefined) {
      throw new Error("the example scene has no plant");
    }
    const { position, rotation } = entity.transform;

    expect(placement(entity.transform)).toEqual({
      position: [position.x, position.y, position.z],
      quaternion: [rotation.x, rotation.y, rotation.z, rotation.w],
    });
  });

  it("has a renderer for every kind the simulator publishes", () => {
    const kinds = SNAPSHOT_SCHEMA.$defs.SceneEntityKind.enum;

    expect(Object.keys(RENDERERS).sort()).toEqual([...kinds].sort());
  });

  it("says what was drawn, and why a scene was not", () => {
    const loaded = renderToStaticMarkup(
      <SceneStatus source={{ kind: "example" }} state={{ status: "loaded", snapshot: EXAMPLE }} />,
    );
    const rejected = renderToStaticMarkup(
      <SceneStatus
        source={{ kind: "scenario", scenarioId: "gh_demo" }}
        state={{
          status: "rejected",
          problems: ["/entities/0/kind must be equal to one of the allowed values"],
        }}
      />,
    );

    expect(loaded).toContain(`gh_demo, day 9, ${EXAMPLE.entities.length} entities`);
    expect(rejected).toContain('role="alert"');
    expect(rejected).toContain("/entities/0/kind must be equal to one of the allowed values");
  });
});
