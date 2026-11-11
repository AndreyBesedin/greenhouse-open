import { expect, type Page } from "@playwright/test";
import { replayAddress } from "../src/landing/paths";

/** A stored run's epoch, as the simulator names it. */
export interface AskedRun {
  runId: string;
  epoch: number;
}

/** A run of `scenario` asked of a worker through the simulator's API, as a
 * scenario's dialog asks for one (P17.7): at `seed`, and as fast as it computes
 * unless `secondsPerDay` paces it, over its scenario's days or `days` fewer
 * (decision 0075). Each test asks for a run of its own, so that
 * none watches what another changes. */
export async function askForRun(
  page: Page,
  scenario: string,
  { seed, secondsPerDay, days }: { seed: number; secondsPerDay?: number; days?: number },
): Promise<AskedRun> {
  const pace = secondsPerDay === undefined ? "" : `&seconds_per_day=${secondsPerDay}`;
  const fewer = days === undefined ? "" : `&duration_days=${days}`;
  const response = await page.request.post(
    `/api/scenarios/${encodeURIComponent(scenario)}/runs?seed=${seed}${pace}${fewer}`,
  );
  expect(response.ok(), await response.text()).toBe(true);
  const { run_id: runId, epoch } = (await response.json()) as { run_id: string; epoch: number };
  return { runId, epoch };
}

function epochPath({ runId, epoch }: AskedRun): string {
  return `/api/runs/${encodeURIComponent(runId)}/epochs/${epoch}`;
}

/** Waits until the run has been computed `timeS` seconds into it, or to its
 * end if it ends first. */
export async function computedTo(
  page: Page,
  run: AskedRun,
  timeS: number,
  timeout: number,
): Promise<void> {
  await expect
    .poll(
      async () => {
        const epoch = (await (await page.request.get(epochPath(run))).json()) as {
          frontier_s: number;
          duration_s: number;
        };
        return epoch.frontier_s >= Math.min(timeS, epoch.duration_s);
      },
      { timeout },
    )
    .toBe(true);
}

/** Stops the run if it is still computed, so that it leaves the workers to the
 * tests after it; one that has ended is left as it is. */
export async function stopRun(page: Page, run: AskedRun): Promise<void> {
  await page.request.post(`${epochPath(run)}/stop`);
}

/** Opens the run's replay at its start, and waits for its timeline. */
export async function openReplay(page: Page, run: AskedRun): Promise<void> {
  await page.goto(replayAddress(run.runId, run.epoch));
  await expect(page.getByRole("slider", { name: "Position in the run" })).toBeVisible({
    timeout: 60_000,
  });
}
