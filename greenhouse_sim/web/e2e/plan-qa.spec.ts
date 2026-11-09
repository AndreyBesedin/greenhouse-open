import { expect, type Page, test } from "@playwright/test";
import { DAY_S } from "../src/clock.ts";
import { type AskedRun, askForRun, computedTo, openReplay, stopRun } from "./replays";

// P13's final scenario, what of it a person sees in the viewer
// (`docs/roadmap/archive/p13-actions.md`): plans given to a run of the reference
// greenhouse's while a worker computes it, through its changes (decision 0073),
// and its replay's plan lane saying what its outcome log says of each action
// (P22.3, decision 0074). What the gateway decides is held where the code is
// (`greenhouse_sim/tests/test_plan_final_qa.py`).

const SCENARIO = "reference_greenhouse";
const PLANT = `${SCENARIO}_plant_030`;
const ME = { kind: "person", id: "local_operator" };
const ARRIVES = { timeout: 90_000 };
const HOUR_S = 3600;
// Slow enough that the plans are given before the moments they name: an hour
// of the run is two and a half seconds.
const SECONDS_PER_DAY = 60;
// How long the worker may take to answer a change it is asked.
const ANSWERED = { timeout: 30_000 };
// The moments the plans name, in hours into the run.
const WARM_AT_H = 8;
const VENT_FROM_H = 9;
const TOO_LATE_S = 60;
const SEEN_AT_H = 12;

interface Outcome {
  plan_id: string;
  ref: { action_id: string };
  status: string;
  event_id?: string | null;
}

function epochPath({ runId, epoch }: AskedRun): string {
  return `/api/runs/${encodeURIComponent(runId)}/epochs/${epoch}`;
}

/** The instant the run's clock started at, as a position over it says. */
async function startedAt(page: Page, run: AskedRun): Promise<string> {
  const opened = await page.request.post(`${epochPath(run)}/positions`);
  expect(opened.ok()).toBe(true);
  const position = (await opened.json()) as { position_id: string; started_at: string };
  await page.request.post(`/api/positions/${position.position_id}/close`);
  return position.started_at;
}

/** Gives the running epoch a plan through its changes, as the local operator,
 * and waits for its worker to be done with it: why it refused it, or null, and
 * the moment of the epoch's clock it was taken at, if it was. */
async function give(
  page: Page,
  run: AskedRun,
  planId: string,
  actions: {
    action_id: string;
    action: object;
    timing: object;
    after?: string[];
    lateness?: object;
  }[],
): Promise<{ refused: string | null; givenS: number | null }> {
  const asked = await page.request.post(`${epochPath(run)}/changes`, {
    data: {
      kind: "plan",
      plan: {
        plan_id: planId,
        run_id: run.runId,
        epoch: run.epoch,
        revision: 1,
        actions: actions.map((each) => ({ ...each, proposed_by: ME })),
      },
    },
  });
  expect(asked.ok(), await asked.text()).toBe(true);
  const { request } = (await asked.json()) as { request: string };
  let answered = { refused: null as string | null, givenS: null as number | null };
  await expect
    .poll(async () => {
      const changes = (await (await page.request.get(`${epochPath(run)}/changes`)).json()) as {
        done: string[];
        refused: { request: string; reason: string }[];
        log: { request?: string | null; given_s: number }[];
      };
      answered = {
        refused: changes.refused.find((answer) => answer.request === request)?.reason ?? null,
        givenS: changes.log.find((entry) => entry.request === request)?.given_s ?? null,
      };
      return changes.done.includes(request);
    }, ANSWERED)
    .toBe(true);
  return answered;
}

/** The outcomes the epoch delivered by `atS` seconds into its run. */
async function outcomes(page: Page, run: AskedRun, atS: number): Promise<Outcome[]> {
  const response = await page.request.get(`${epochPath(run)}/outcomes?t=${atS}`);
  expect(response.ok()).toBe(true);
  return ((await response.json()) as { outcomes: Outcome[] }).outcomes;
}

/** Moves the replay to `hours` into the run, an hour at a time from its start,
 * and waits for the moment to be drawn there. */
async function replayTo(page: Page, days: number, hours: number): Promise<void> {
  const handle = page.getByRole("slider", { name: "Position in the run" });
  await handle.focus();
  await page.keyboard.press("Home");
  for (let day = 0; day < days; day += 1) {
    await page.keyboard.press("PageUp");
  }
  for (let hour = 0; hour < hours; hour += 1) {
    await page.keyboard.press("ArrowRight");
  }
  await expect(handle).toHaveAttribute(
    "aria-valuetext",
    `Day ${days + 1}, ${String(hours).padStart(2, "0")}:00`,
    ARRIVES,
  );
}

test("a plan carried out, late, on time and refused: the replay's plan lane says what its outcome log holds (P13.10)", async ({
  page,
}) => {
  test.setTimeout(420_000);
  const run = await askForRun(page, SCENARIO, { seed: 69, secondsPerDay: SECONDS_PER_DAY });
  try {
    const start = await startedAt(page, run);
    const at = (timeS: number) => ({
      kind: "at",
      at: new Date(Date.parse(start) + timeS * 1000).toISOString(),
    });

    await test.step("a plan as the local operator: a target, a window, and a harvest then a lowering", async () => {
      const { refused } = await give(page, run, "qa", [
        {
          action_id: "warm_day",
          action: { kind: "set_target", target: "heating_day", value_c: 22 },
          timing: at(WARM_AT_H * HOUR_S),
        },
        {
          action_id: "harvest",
          action: { kind: "harvest", plant_id: PLANT, scope: "truss", organ_id: `${PLANT}_t01` },
          timing: { kind: "asap" },
        },
        {
          action_id: "lower",
          action: { kind: "lower", plant_id: PLANT, by_cm: 10 },
          timing: { kind: "asap" },
          after: ["harvest"],
        },
        {
          action_id: "open_vent",
          action: { kind: "set_level", device_id: "roof_vent_1", level: 1 },
          timing: {
            kind: "window",
            not_before: at(VENT_FROM_H * HOUR_S).at,
            not_after: at((VENT_FROM_H + 0.5) * HOUR_S).at,
          },
        },
      ]);
      expect(refused).toBeNull();
    });

    await test.step("a harvest within the day is refused when given, saying why", async () => {
      const { refused } = await give(page, run, "at_14", [
        {
          action_id: "harvest_at_14",
          action: { kind: "harvest", plant_id: PLANT, scope: "ripe" },
          timing: at(14 * HOUR_S),
        },
      ]);
      expect(refused).toMatch(/at a day's start/);
    });

    // Its first day computed, the replay shows it at noon, past every moment
    // the plans name in it.
    await computedTo(page, run, DAY_S, 240_000);
    await openReplay(page, run);
    await replayTo(page, 0, SEEN_AT_H);
    await page.locator("details.timeline").getByText("Timeline").click();
    await page.getByRole("combobox", { name: "Timeline zoom" }).selectOption({ label: "a day" });
    const entries = page.getByTestId("timeline-plan-entry");
    const entry = (text: RegExp) => entries.filter({ hasText: text });

    await test.step("the lane says what became of each, as the epoch's outcome log holds it", async () => {
      await expect(entry(/\(qa\/warm_day\): executed$/)).toHaveCount(1, ARRIVES);
      await expect(entry(/\(qa\/open_vent\): executed$/)).toHaveCount(1, ARRIVES);
      await expect(entry(/\(at_14\/harvest_at_14\): refused: .* at a day's start/)).toHaveCount(1);
      for (const { plan_id, ref, status } of await outcomes(page, run, SEEN_AT_H * HOUR_S)) {
        await expect(entry(new RegExp(`\\(${plan_id}/${ref.action_id}\\): ${status}`))).toHaveCount(
          1,
        );
      }
    });

    // Given once the epoch's clock has passed its first day: a worker takes a
    // change at its own clock, not at the moment the replay shows (decision 0073).
    let criticalS = DAY_S;
    await test.step("a critical action due already is missed, and what waits for it cancelled", async () => {
      const { givenS } = await give(page, run, "critical", [
        {
          action_id: "too_late",
          action: { kind: "set_level", device_id: "door", level: 1 },
          timing: at(TOO_LATE_S),
          lateness: { tolerance_s: 0, on_late: "critical" },
        },
        {
          action_id: "waits",
          action: { kind: "set_level", device_id: "fan_left", level: 0.5 },
          timing: { kind: "asap" },
          after: ["too_late"],
        },
      ]);
      expect(givenS).toBeGreaterThanOrEqual(DAY_S);
      criticalS = givenS ?? DAY_S;
    });

    await test.step("the crop's work at the next day's start, its events naming their actions", async () => {
      // Shown on its second day, an hour past both the crop's work and the
      // critical plan's answer.
      const hour = Math.max(1, Math.ceil((criticalS - DAY_S) / HOUR_S) + 1);
      await computedTo(page, run, 2 * DAY_S, 240_000);
      await replayTo(page, 1, hour);
      await expect(entry(/\(qa\/harvest\): executed$/)).toHaveCount(1, ARRIVES);
      await expect(entry(/\(qa\/lower\): executed$/)).toHaveCount(1, ARRIVES);
      await expect(entry(/\(critical\/too_late\): missed: late$/)).toHaveCount(1, ARRIVES);
      await expect(entry(/\(critical\/waits\): cancelled: its prerequisite/)).toHaveCount(1);
      const atS = DAY_S + hour * HOUR_S;
      const events = (await (
        await page.request.get(`${epochPath(run)}/events?t=${atS}`)
      ).json()) as { events: { event_id: string; parameters: { action?: string } }[] };
      const named = new Map(events.events.map((each) => [each.event_id, each.parameters.action]));
      for (const { ref, event_id } of (await outcomes(page, run, atS)).filter(({ ref }) =>
        ["harvest", "lower"].includes(ref.action_id),
      )) {
        expect(named.get(event_id ?? "")).toBe(ref.action_id);
      }
    });
  } finally {
    await stopRun(page, run);
  }
});
