/** A value a test needs to be there, such as a fixture's entity: if it is
 * missing, the test fails saying what it needed, rather than reading through
 * a type assertion. */
export function present<T>(value: T | undefined, what: string): T {
  if (value === undefined) {
    throw new Error(`the test needs ${what}, which is missing`);
  }
  return value;
}
