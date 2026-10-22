/**
 * What the viewer fetches from the simulator, checked (AUDIT.8, W12): one
 * way to fetch a document and read it, beside `useLoad`, which keeps its
 * state, and one way to check it against the contract the simulator
 * publishes for it.
 */

import Ajv2020, { type SchemaObject, type ValidateFunction } from "ajv/dist/2020";

/** A document fetched and read, or why there is none. */
export type Loaded<T> = { status: "loaded"; value: T } | { status: "unavailable"; reason: string };

/** Why an answer that is not OK was refused, by default: its status. */
async function answered(response: Response): Promise<string> {
  return `the simulator API answered ${response.status}`;
}

/**
 * The document at `url`, as `parse` reads its JSON; every failure becomes
 * `unavailable`, with why: an answer that is not OK (as `refused` says it,
 * by default its status), one that is not JSON, or one `parse` refuses by
 * throwing. A loader turns the value into its own state.
 */
export async function loadJson<T>(
  url: string,
  parse: (body: unknown) => T,
  fetchFn: typeof fetch = fetch,
  refused: (response: Response) => Promise<string> = answered,
): Promise<Loaded<T>> {
  try {
    const response = await fetchFn(url);
    if (!response.ok) {
      return { status: "unavailable", reason: await refused(response) };
    }
    return { status: "loaded", value: parse(await response.json()) };
  } catch (error) {
    return {
      status: "unavailable",
      reason: error instanceof Error ? error.message : String(error),
    };
  }
}

// One validator for every contract the simulator publishes, each generated
// into its area's `generated` folder (`npm run generate`). A format, such as
// an instant's `date-time`, is read as the text it is, not checked.
const contracts = new Ajv2020({ allErrors: true, strict: true, validateFormats: false });

/** A body as its contract describes it, or what is wrong with it, each
 * problem where it lies in the body. */
export type Checked<T> = { ok: true; value: T } | { ok: false; problems: string[] };

/** A check of a body against a schema the simulator publishes, rather than
 * trust; `what` names the body, for a problem with the whole of it. The
 * schema is compiled when it is first checked against. */
export function contractCheck<T>(
  schema: SchemaObject,
  what: string,
): (body: unknown) => Checked<T> {
  let validate: ValidateFunction<T> | undefined;
  return (body) => {
    validate ??= contracts.compile<T>(schema);
    if (validate(body)) {
      return { ok: true, value: body };
    }
    const problems = (validate.errors ?? []).map(
      (error) => `${error.instancePath || what} ${error.message ?? "is not valid"}`,
    );
    return { ok: false, problems };
  };
}

/** A reader of a body its contract describes: the body, or an error that
 * says `refusal`, the loader's own words for a body it cannot read. */
export function contractReader<T>(schema: SchemaObject, refusal: string): (body: unknown) => T {
  const check = contractCheck<T>(schema, "the body");
  return (body) => {
    const checked = check(body);
    if (!checked.ok) {
      throw new Error(refusal);
    }
    return checked.value;
  };
}

// What has no contract is read by hand: the reference QA's file, which a
// test writes rather than a service, and whose parts are each checked
// against their own contracts.

/** Whether a value read from the wire is an object, to read its fields. */
export function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/** Whether a value is an object of numbers by name, not a list. */
export function isNumberRecord(value: unknown): value is Record<string, number> {
  return (
    isObject(value) &&
    !Array.isArray(value) &&
    Object.values(value).every((entry) => typeof entry === "number")
  );
}
