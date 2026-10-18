// Where the simulator's local API listens. The dev and preview servers
// forward /api to it: on the API's own default port
// (`python -m greenhouse_sim.api`), or on the one SIMULATOR_API_PORT names.
export const DEFAULT_SIMULATOR_API_PORT = 8765;
// The browser tests start their own API on this port, apart from one a
// developer keeps running on the default port, which cannot answer for them.
export const TEST_SIMULATOR_API_PORT = 8766;

export function simulatorApi(port: number): string {
  return `http://127.0.0.1:${port}`;
}

// The interpreter the browser tests serve the simulator from, which has
// greenhouse-sim installed: `uv run browser-tests` names the workspace's.
const PYTHON = process.env.PYTHON ?? "python";

/** The shell command that serves the simulator's API on `port`, from
 * `python`, which is quoted: a clone's path may hold a space. */
export function simulatorServer(port: number, python: string = PYTHON): string {
  return `${shellWord(python)} -m greenhouse_sim.api --port ${port}`;
}

/** `text` as one word to a POSIX shell. */
export function shellWord(text: string): string {
  return `'${text.replaceAll("'", `'"'"'`)}'`;
}

// The browser tests start their own servers, and never trust one already
// running on their ports: an older simulator, or another checkout's build,
// would be tested in their place, and Playwright stops instead. Set
// REUSE_TEST_SERVERS=1 to reuse them deliberately, to rerun a test quickly
// against servers known to be this checkout's. CI never reuses them.
export const REUSE_TEST_SERVERS =
  process.env.REUSE_TEST_SERVERS === "1" && process.env.CI === undefined;
