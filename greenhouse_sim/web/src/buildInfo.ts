// Filled in by Vite at build time (see vite.config.ts).
declare const __SIMULATOR_VERSION__: string;
declare const __SOURCE_COMMIT__: string;
declare const __SOURCE_BRANCH__: string;

export interface BuildInfo {
  simulatorVersion: string;
  sourceCommit: string;
  /** The branch built from: `HEAD` when none was checked out, as at a release's
   * tag, or `unknown` outside a checkout. */
  sourceBranch: string;
}

export const buildInfo: BuildInfo = {
  simulatorVersion: __SIMULATOR_VERSION__,
  sourceCommit: __SOURCE_COMMIT__,
  sourceBranch: __SOURCE_BRANCH__,
};

// The branches a build says no more of than its version (P22.8): the main line,
// and none, as a release's tag and CI's checkouts are.
const UNNAMED_BRANCHES: ReadonlySet<string> = new Set(["main", "HEAD", "unknown"]);

/** What the viewer was built from, in a line: its version, and on a branch of
 * its own, that branch and the commit, which a version alone does not name. */
export function describeBuild({ simulatorVersion, sourceCommit, sourceBranch }: BuildInfo): string {
  return UNNAMED_BRANCHES.has(sourceBranch)
    ? `simulator ${simulatorVersion}`
    : `simulator ${simulatorVersion} · ${sourceBranch} at ${sourceCommit}`;
}
