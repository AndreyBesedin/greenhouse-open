// Where the simulator's local API listens (`python -m greenhouse_sim.api`,
// whose default port this matches). The dev and preview servers forward /api
// here, and the browser smoke test starts it here.
export const SIMULATOR_API_PORT = 8765;
export const SIMULATOR_API = `http://127.0.0.1:${SIMULATOR_API_PORT}`;
