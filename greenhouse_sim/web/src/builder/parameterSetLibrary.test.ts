import { describe, expect, it } from "vitest";

import {
  changedValue,
  newVersion,
  parseParametersSchema,
  parseSets,
  refusedByField,
  type SetRead,
  saveSet,
  type VersionForm,
} from "./parameterSetLibrary";

const DIGEST = `sha256:${"a".repeat(64)}`;

/** Reduced-State TOMGRO's published set, three of its values. */
const PUBLISHED: SetRead = {
  model: "reduced_tomgro",
  name: "gnvman",
  version: 1,
  digest: DIGEST,
  based_on: null,
  made_for: 1,
  cultivar: null,
  description: "",
  published: true,
  parameters: { alpha_f: 0.8, qe: 0.0645, d: 2.5926912 },
  why: {},
  values: { alpha_f: 0.8, qe: 0.0645, d: 2.5926912 },
};

const FORM: VersionForm = {
  name: " brighter ",
  cultivar: " ",
  description: " More light. ",
  values: { alpha_f: "0.80", qe: " 0.08 ", d: "" },
  why: { alpha_f: "never sent", qe: " a calibration " },
};

/** A fetch that answers every request with `status` and `body`, and keeps
 * what it was sent. */
function answering(status: number, body: unknown, sent: RequestInit[] = []): typeof fetch {
  return async (_input, init) => {
    sent.push(init ?? {});
    return new Response(typeof body === "string" ? body : JSON.stringify(body), { status });
  };
}

describe("a new version of a parameter set, as the form saves it (P20.5)", () => {
  it("gives only the values that differ from its base's, each with why", () => {
    const file = newVersion(PUBLISHED, FORM, 3);

    expect(file).toEqual({
      model: "reduced_tomgro",
      name: "brighter",
      based_on: { name: "gnvman", version: 1, digest: DIGEST },
      parameters: { qe: 0.08 },
      why: { qe: "a calibration" },
      made_for: 3,
      cultivar: null,
      description: "More light.",
    });
    expect(file).not.toHaveProperty("version");
  });

  it("sends a value changed with no why as one, for the simulator to refuse", () => {
    const file = newVersion(PUBLISHED, { ...FORM, why: {}, cultivar: "Moneymaker" }, 1);

    expect(file.why).toEqual({ qe: "" });
    expect(file.cultivar).toBe("Moneymaker");
  });

  it("takes a value left empty, or as its base gives it, as unchanged", () => {
    expect(changedValue("", 1)).toBeNull();
    expect(changedValue(undefined, 1)).toBeNull();
    expect(changedValue("1.0", 1)).toBeNull();
    expect(changedValue("2", 1)).toBe(2);
    // What reads as no number is sent as one the simulator says is not.
    expect(changedValue("x", 1)).toBeNaN();
  });
});

describe("a parameter set's answers, checked (P20.4)", () => {
  it("refuses a list that is not one of sets", () => {
    const { parameters: _, why: __, values: ___, ...listed } = PUBLISHED;

    expect(parseSets([listed])).toEqual([listed]);
    expect(() => parseSets({})).toThrow("expected a list of parameter sets");
    expect(() => parseSets([{ ...listed, digest: 1 }])).toThrow("set 0 is not a parameter set");
  });

  it("refuses a schema of parameters with no properties", () => {
    const schema = { properties: { qe: { type: "number" } } };

    expect(parseParametersSchema(schema)).toBe(schema);
    expect(() => parseParametersSchema({ properties: [] })).toThrow("not the schema");
    expect(() => parseParametersSchema(null)).toThrow("not the schema");
  });
});

describe("a save of a new version, answered", () => {
  it("is the set the simulator kept, sent as JSON to its model's sets", async () => {
    const { parameters: _, why: __, values: ___, ...listed } = PUBLISHED;
    const sent: RequestInit[] = [];
    const saved = await saveSet(
      "reduced_tomgro",
      newVersion(PUBLISHED, FORM, 1),
      answering(200, { ...listed, name: "brighter", published: false }, sent),
    );

    expect(saved).toMatchObject({ ok: true, value: { name: "brighter", version: 1 } });
    expect(sent[0]?.method).toBe("POST");
    expect(JSON.parse(String(sent[0]?.body))).toMatchObject({ parameters: { qe: 0.08 } });
  });

  it("is refused as a whole and by field, in the simulator's words", async () => {
    const refused = await saveSet(
      "reduced_tomgro",
      newVersion(PUBLISHED, FORM, 1),
      answering(400, {
        error: "parameters.qe: Input should be greater than or equal to 0",
        problems: [
          { field: "parameters.qe", message: "Input should be greater than or equal to 0" },
          { field: 3, message: "not a field's" },
        ],
      }),
    );

    expect(refused).toEqual({
      ok: false,
      problem: "parameters.qe: Input should be greater than or equal to 0",
      fields: { "parameters.qe": "Input should be greater than or equal to 0" },
    });
  });

  it("says the status of a refusal that says nothing readable, or why it was not sent", async () => {
    expect(await refusedByField(new Response("down", { status: 502 }))).toEqual({
      problem: "the simulator API answered 502",
      fields: {},
    });
    const failing: typeof fetch = async () => {
      throw new Error("offline");
    };
    expect(await saveSet("reduced_tomgro", newVersion(PUBLISHED, FORM, 1), failing)).toEqual({
      ok: false,
      problem: "offline",
      fields: {},
    });
  });
});
