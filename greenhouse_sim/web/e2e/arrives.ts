import { expect as playwrightExpect } from "@playwright/test";

// How long what the simulator works out may take to reach the page. A run's
// moment, and the equipment, charts and weather asked for beside it, wait
// their turn behind each other on a loaded machine, so that the default five
// seconds say more about the machine than about the view.
const ARRIVES_MS = 40_000;

/** How long a test may take that waits for several such answers in turn. */
export const WAITS_FOR_THE_SIMULATOR_MS = 180_000;

/** `expect`, for what is asked of the simulator: the same values, given as
 * long as a loaded machine may take to answer. */
export const expect = playwrightExpect.configure({ timeout: ARRIVES_MS });
