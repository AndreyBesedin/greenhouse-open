// What P09's golden views of the reference greenhouse show, kept free of
// imports so that browser tests can read it too (`referenceViews.ts` draws
// them).

export const QA_REFERENCE_PATH = "/qa/reference-greenhouse";
export const QA_REFERENCE_VIEWS = [
  "dawn",
  "noon",
  "evening",
  "fans-on",
  "fans-off",
  "vents-open",
  "vents-closed",
  "young",
  "fruiting",
  "camera-rgb",
  "camera-depth",
  "airflow-slice",
  "radiation-slice",
] as const;
export type QaReferenceView = (typeof QA_REFERENCE_VIEWS)[number];
