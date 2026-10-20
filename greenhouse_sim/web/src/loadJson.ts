/**
 * What the viewer fetches from the simulator, checked (AUDIT.8, W12): one
 * way to fetch a document and read it, beside `useLoad`, which keeps its
 * state, and the checks the readers of the wire share.
 */

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

/** Whether a value read from the wire is an object, to read its fields. */
export function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/** Whether a value is a list of numbers, of `length` if given. */
export function isNumberList(value: unknown, length?: number): value is number[] {
  return (
    Array.isArray(value) &&
    (length === undefined || value.length === length) &&
    value.every((item) => typeof item === "number")
  );
}

/** Whether a value is an object of numbers by name, not a list. */
export function isNumberRecord(value: unknown): value is Record<string, number> {
  return (
    isObject(value) &&
    !Array.isArray(value) &&
    Object.values(value).every((entry) => typeof entry === "number")
  );
}
