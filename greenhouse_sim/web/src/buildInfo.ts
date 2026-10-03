// Filled in by Vite at build time (see vite.config.ts).
declare const __SIMULATOR_VERSION__: string;
declare const __SOURCE_COMMIT__: string;

export interface BuildInfo {
  simulatorVersion: string;
  sourceCommit: string;
}

export const buildInfo: BuildInfo = {
  simulatorVersion: __SIMULATOR_VERSION__,
  sourceCommit: __SOURCE_COMMIT__,
};
