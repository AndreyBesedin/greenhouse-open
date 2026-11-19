/**
 * A crop model's parameter sets as the simulator keeps and serves them (P20.4,
 * decision 0077), for the builder's form for a set (P20.5): a model's sets,
 * the schema of its parameters, one set read with every value it resolves to,
 * a new version saved, two compared, and a set's file. Each answer is checked
 * against the contract the simulator publishes for it; what a set may hold is
 * the simulator's to say, by field.
 */

import { contractCheck, contractReader, isObject, type Loaded, loadJson } from "../loadJson";
import { refusal } from "./api";
import { PARAMETER_SET_COMPARISON_SCHEMA } from "./generated/parameterSetComparisonSchema";
import type { SetComparison } from "./generated/parameterSetComparisonTypes";
import { PARAMETER_SET_DOWNLOAD_SCHEMA } from "./generated/parameterSetDownloadSchema";
import type { SetDownload } from "./generated/parameterSetDownloadTypes";
import { PARAMETER_SET_LISTED_SCHEMA } from "./generated/parameterSetListedSchema";
import type { SetListed, SetNamed } from "./generated/parameterSetListedTypes";
import { PARAMETER_SET_READ_SCHEMA } from "./generated/parameterSetReadSchema";
import type { SetRead } from "./generated/parameterSetReadTypes";
import type { ParameterSet } from "./generated/parameterSetTypes";

export type { SetComparison, SetDownload, SetListed, SetNamed, SetRead };

export const PARAMETER_SETS_URL = "/api/parameter-sets";

/** A set as its model's sets are looked up by: its name and version. */
export interface SetKey {
  name: string;
  version: number;
}

/** A set's file as a save sends it: without its version, which the save
 * gives it, its name's next; of the model its base is a set of, which the
 * simulator checks is one that has sets. */
export type NewVersion = Omit<ParameterSet, "version" | "model"> & { model: string };

/** A save's answer: the set kept, or why it was refused, as a whole and by
 * field, as the simulator names each (`parameters.qe`, `why.qe`, `name`). */
export type Saved =
  | { ok: true; value: SetListed }
  | { ok: false; problem: string; fields: Readonly<Record<string, string>> };

/** Where a model's sets, or one of them, or what is asked of it, are served. */
function setsUrl(model: string, ...parts: readonly (string | number)[]): string {
  return [PARAMETER_SETS_URL, ...[model, ...parts].map((part) => encodeURIComponent(part))].join(
    "/",
  );
}

const checkListed = contractCheck<SetListed>(PARAMETER_SET_LISTED_SCHEMA, "the set");
const readListed = contractReader<SetListed>(PARAMETER_SET_LISTED_SCHEMA, "not a parameter set");
const readSet = contractReader<SetRead>(PARAMETER_SET_READ_SCHEMA, "not a parameter set");
const readComparison = contractReader<SetComparison>(
  PARAMETER_SET_COMPARISON_SCHEMA,
  "not a comparison of two parameter sets",
);
const readDownload = contractReader<SetDownload>(
  PARAMETER_SET_DOWNLOAD_SCHEMA,
  "not a parameter set's file",
);

/** A model's sets in a response body, checked rather than trusted. */
export function parseSets(body: unknown): SetListed[] {
  if (!Array.isArray(body)) {
    throw new Error("expected a list of parameter sets");
  }
  return body.map((item: unknown, index) => {
    const checked = checkListed(item);
    if (!checked.ok) {
      throw new Error(`set ${index} is not a parameter set`);
    }
    return checked.value;
  });
}

/** The schema of a model's parameters in a response body: a JSON Schema whose
 * properties `parameterFields` reads, each as far as it says. */
export function parseParametersSchema(body: unknown): Record<string, unknown> {
  if (!isObject(body) || !isObject(body.properties) || Array.isArray(body.properties)) {
    throw new Error("not the schema of a model's parameters");
  }
  return body;
}

/** A model's sets, its published one first; not found for a model that has
 * none, which the simulator's refusal says. */
export function loadSets(
  model: string,
  fetchFn: typeof fetch = fetch,
): Promise<Loaded<SetListed[]>> {
  return loadJson(setsUrl(model), parseSets, fetchFn, refusal);
}

/** The schema of a model's parameters, as the simulator publishes it. */
export function loadParametersSchema(
  model: string,
  fetchFn: typeof fetch = fetch,
): Promise<Loaded<Record<string, unknown>>> {
  return loadJson(setsUrl(model, "schema"), parseParametersSchema, fetchFn, refusal);
}

/** One of a model's sets, with every value it resolves to. */
export function loadSet(
  model: string,
  { name, version }: SetKey,
  fetchFn: typeof fetch = fetch,
): Promise<Loaded<SetRead>> {
  return loadJson(setsUrl(model, name, version), readSet, fetchFn, refusal);
}

/** Two of a model's sets, parameter by parameter: `first`'s values first. */
export function compareSets(
  model: string,
  first: SetKey,
  second: SetKey,
  fetchFn: typeof fetch = fetch,
): Promise<Loaded<SetComparison>> {
  const url = setsUrl(model, first.name, first.version, "compare", second.name, second.version);
  return loadJson(url, readComparison, fetchFn, refusal);
}

/** A set's file, as the simulator writes it, to download. */
export function downloadSet(
  model: string,
  { name, version }: SetKey,
  fetchFn: typeof fetch = fetch,
): Promise<Loaded<SetDownload>> {
  return loadJson(setsUrl(model, name, version, "file"), readDownload, fetchFn, refusal);
}

/** Why the simulator refused a save: its `error`, and its `problems` by the
 * field each names; or its status, if it said nothing readable. */
export async function refusedByField(
  response: Response,
): Promise<{ problem: string; fields: Record<string, string> }> {
  const fields: Record<string, string> = {};
  try {
    const body: unknown = await response.json();
    const problems = isObject(body) && Array.isArray(body.problems) ? body.problems : [];
    for (const each of problems) {
      if (isObject(each) && typeof each.field === "string" && typeof each.message === "string") {
        fields[each.field] = each.message;
      }
    }
    if (isObject(body) && typeof body.error === "string") {
      return { problem: body.error, fields };
    }
  } catch {
    // Not JSON: its status says it.
  }
  return { problem: `the simulator API answered ${response.status}`, fields };
}

/** A set's file saved as its name's next version, or answered as the version
 * of its name that has its numbers already. */
export async function saveSet(
  model: string,
  file: NewVersion,
  fetchFn: typeof fetch = fetch,
): Promise<Saved> {
  try {
    const response = await fetchFn(setsUrl(model), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(file),
    });
    if (!response.ok) {
      return { ok: false, ...(await refusedByField(response)) };
    }
    return { ok: true, value: readListed(await response.json()) };
  } catch (error) {
    return {
      ok: false,
      problem: error instanceof Error ? error.message : String(error),
      fields: {},
    };
  }
}

/** What a form for a new version holds: its name, the cultivar and the words
 * it is described in, each parameter's value as typed, and why each changed
 * one is what it is. */
export interface VersionForm {
  name: string;
  cultivar: string;
  description: string;
  values: Readonly<Record<string, string>>;
  why: Readonly<Record<string, string>>;
}

/** The value typed for a parameter, if it differs from its base's: a number
 * as a number, so that the simulator says what is wrong with it; nothing for
 * a field left empty or as its base has it. */
export function changedValue(typed: string | undefined, base: number): number | null {
  const text = (typed ?? "").trim();
  if (text === "") {
    return null;
  }
  const value = Number(text);
  return value === base ? null : value;
}

/** The file a form saves: based on `base`, giving the values that differ
 * from its, each with why; made for the version of the model the simulator
 * runs, `madeFor`, which its published set gives. */
export function newVersion(base: SetRead, form: VersionForm, madeFor: number): NewVersion {
  const parameters: Record<string, number> = {};
  const why: Record<string, string> = {};
  for (const [name, value] of Object.entries(base.values)) {
    const changed = changedValue(form.values[name], value);
    if (changed !== null) {
      parameters[name] = changed;
      why[name] = (form.why[name] ?? "").trim();
    }
  }
  const cultivar = form.cultivar.trim();
  return {
    model: base.model,
    name: form.name.trim(),
    based_on: { name: base.name, version: base.version, digest: base.digest },
    parameters,
    why,
    made_for: madeFor,
    cultivar: cultivar === "" ? null : cultivar,
    description: form.description.trim(),
  };
}

/** A set as it is told to a person: "gnvman v1". */
export function setName({ name, version }: SetKey): string {
  return `${name} v${version}`;
}
