// What the renderer's canonical screenshot page shows, kept free of imports so
// that browser tests can read it too.

export const QA_RENDERER_PATH = "/qa/renderer";
export const DEFAULT_QA_SEED = 42;
// The plant the page selects and the property it colours by.
export const QA_SELECTED_ID = "qa_plant_08";
export const QA_COLOUR_PROPERTY = "height_cm";

/** The seed a QA address asks for: a whole number, or the default without one. */
export function qaSeed(search: string): number | null {
  const value = new URLSearchParams(search).get("seed");
  if (value === null) {
    return DEFAULT_QA_SEED;
  }
  return /^\d+$/.test(value) ? Number(value) : null;
}
