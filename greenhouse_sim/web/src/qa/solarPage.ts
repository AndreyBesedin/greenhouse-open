// What P08's equinox views show, kept free of imports so that browser tests
// can read it too (`solarViews.ts` draws them).

export const QA_SOLAR_PATH = "/qa/solar-lab";
export const QA_SOLAR_VIEWS = ["morning", "noon", "evening"] as const;
export type QaSolarView = (typeof QA_SOLAR_VIEWS)[number];
