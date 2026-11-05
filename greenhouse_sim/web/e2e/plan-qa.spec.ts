import { expect, type Page, test } from "@playwright/test";
import { DAY_S } from "../src/clock.ts";

// P13's final scenario, what of it a person sees in the viewer
// (`docs/roadmap/p13-actions.md`): a plan given to the reference greenhouse's
// playing run, and its plan lane saying what the consumer interface says of
// each action. What the gateway decides is held where the code is
// (`greenhouse_sim/tests/test_plan_final_qa.py`).

const SCENARIO = "reference_greenhouse";
const PLAYBACK = `/api/scenarios/${SCENARIO}/playback`;
const PLANT = `${SCENARIO}_plant_030`;
const ME = { kind: "person", id: "local_operator" };
const ARRIVES = { timeout: 90_000 };
const HOUR_S = 3600;
// Fast enough for the test, slow enough to pause it within the hour.
const SECONDS_PER_DAY = 30;

interface Played {
  run_id: string;
  epoch: number;
  started_at: string;
  time_s: number;
}

interface Outcome {
  plan_id: string;
  ref: { action_id: string };
  status: string;
  event_id?: string | null;
}

async function played(page: Page): Promise<Played> {
  return (await (await page.request.get(PLAYBACK)).json()) as Played;
}

/** Plays the run until its clock passes `timeS`, then pauses it. */
async function playTo(page: Page, timeS: number): Promise<Played> {
  expect((await page.request.post(`${PLAYBACK}/play`)).ok()).toBe(true);
  await expect
    .poll(async () => (await played(page)).time_s, { ...ARRIVES, intervals: [50] })
    .toBeGreaterThanOrEqual(timeS);
  expect((await page.request.post(`${PLAYBACK}/pause`)).ok()).toBe(true);
  return played(page);
}

function at(run: Played, timeS: number): { kind: "at"; at: string } {
  return { kind: "at", at: new Date(Date.parse(run.started_at) + timeS * 1000).toISOString() };
}

async function give(
  page: Page,
  run: Played,
  planId: string,
  actions: {
    action_id: string;
    action: object;
    timing: object;
    after?: string[];
    lateness?: object;
  }[],
): Promise<{ accepted: boolean; refused: { action_id: string }[] }> {
  const response = await page.request.post(`/actuation/v1/runs/${run.run_id}/plans`, {
    data: {
      plan_id: planId,
      run_id: run.run_id,
      epoch: run.epoch,
      revision: 1,
      actions: actions.map((each) => ({ ...each, proposed_by: ME })),
    },
  });
  expect(response.ok()).toBe(true);
  return (await response.json()) as { accepted: boolean; refused: { action_id: string }[] };
}

async function outcomes(page: Page, run: Played): Promise<Outcome[]> {
  const response = await page.request.get(`/consumer/v1/runs/${run.run_id}/outcomes`);
  expect(response.ok()).toBe(true);
  return ((await response.json()) as { outcomes: Outcome[] }).outcomes;
}

test("a plan carried out, late, on time and refused: the plan lane says what a consumer reads (P13.10)", async ({
  page,
}) => {
  test.setTimeout(420_000);
  expect((await page.request.post(`${PLAYBACK}/start?hold=true`)).ok()).toBe(true);
  expect((await page.request.post(`${PLAYBACK}/restart`)).ok()).toBe(true);
  expect((await page.request.post(`${PLAYBACK}/pause`)).ok()).toBe(true);
  expect(
    (await page.request.post(`${PLAYBACK}/pace?seconds_per_day=${SECONDS_PER_DAY}`)).ok(),
  ).toBe(true);

  await page.goto(`/?scenario=${SCENARIO}&field=climate&follow=1`);
  const panel = page.getByRole("region", { name: "Run played back" });
  await expect(panel.getByTestId("playback-status")).toContainText("paused", ARRIVES);
  await page.locator("details.timeline").getByText("Timeline").click();
  await page.getByRole("combobox", { name: "Timeline zoom" }).selectOption({ label: "a day" });
  const entries = page.getByTestId("timeline-plan-entry");
  const entry = (text: RegExp) => entries.filter({ hasText: text });

  // Given when the clock has passed the first's moment, and before the rest.
  const given = await playTo(page, HOUR_S / 4);
  const nextHour = Math.ceil(given.time_s / HOUR_S) + 1;

  await test.step("a plan as the local operator: a target, a window, and a harvest then a lowering", async () => {
    const receipt = await give(page, given, "qa", [
      {
        action_id: "warm_day",
        action: { kind: "set_target", target: "heating_day", value_c: 22 },
        timing: at(given, nextHour * HOUR_S),
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
          not_before: at(given, (nextHour + 1) * HOUR_S).at,
          not_after: at(given, (nextHour + 1.5) * HOUR_S).at,
        },
      },
    ]);
    expect([receipt.accepted, receipt.refused]).toEqual([true, []]);
  });

  await test.step("a critical action due already is missed, and what waits for it cancelled", async () => {
    const receipt = await give(page, given, "critical", [
      {
        action_id: "too_late",
        action: { kind: "set_level", device_id: "door", level: 1 },
        timing: at(given, given.time_s - HOUR_S / 12),
        lateness: { tolerance_s: 0, on_late: "critical" },
      },
      {
        action_id: "waits",
        action: { kind: "set_level", device_id: "fan_left", level: 0.5 },
        timing: { kind: "asap" },
        after: ["too_late"],
      },
    ]);
    expect(receipt.accepted).toBe(true);
  });

  await test.step("a harvest within the day is refused when given, saying why", async () => {
    const receipt = await give(page, given, "at_14", [
      {
        action_id: "harvest_at_14",
        action: { kind: "harvest", plant_id: PLANT, scope: "ripe" },
        timing: at(given, 14 * HOUR_S),
      },
    ]);
    expect(receipt.refused.map(({ action_id }) => action_id)).toEqual(["harvest_at_14"]);
  });

  const morning = await playTo(page, (nextHour + 1.75) * HOUR_S);

  await test.step("the lane says what became of each, as a consumer reads it", async () => {
    await expect(entry(/\(qa\/warm_day\): executed$/)).toHaveCount(1, ARRIVES);
    await expect(entry(/\(qa\/open_vent\): executed$/)).toHaveCount(1, ARRIVES);
    await expect(entry(/\(critical\/too_late\): missed: late$/)).toHaveCount(1, ARRIVES);
    await expect(entry(/\(critical\/waits\): cancelled: its prerequisite/)).toHaveCount(1);
    await expect(entry(/\(at_14\/harvest_at_14\): refused: .* at a day's start/)).toHaveCount(1);
    for (const { plan_id, ref, status } of await outcomes(page, morning)) {
      await expect(entry(new RegExp(`\\(${plan_id}/${ref.action_id}\\): ${status}`))).toHaveCount(
        1,
      );
    }
  });

  const nextDay = await playTo(page, DAY_S + HOUR_S / 4);

  await test.step("the crop's work at the next day's start, its events naming their actions", async () => {
    await expect(entry(/\(qa\/harvest\): executed$/)).toHaveCount(1, ARRIVES);
    await expect(entry(/\(qa\/lower\): executed$/)).toHaveCount(1, ARRIVES);
    const events = (await (
      await page.request.get(`/consumer/v1/runs/${nextDay.run_id}/events`)
    ).json()) as { events: { event_id: string; parameters: { action?: string } }[] };
    const named = new Map(events.events.map((each) => [each.event_id, each.parameters.action]));
    for (const { ref, event_id } of (await outcomes(page, nextDay)).filter(({ ref }) =>
      ["harvest", "lower"].includes(ref.action_id),
    )) {
      expect(named.get(event_id ?? "")).toBe(ref.action_id);
    }
  });

  await test.step("started over, what was still to come is cancelled, and nothing else applies", async () => {
    await give(page, nextDay, "later", [
      {
        action_id: "fan_later",
        action: { kind: "set_level", device_id: "fan_left", level: 0.4 },
        timing: at(nextDay, 3 * DAY_S),
      },
    ]);
    await panel.getByRole("button", { name: "Start over" }).click();
    await expect(panel.getByTestId("playback-status")).toContainText(
      `epoch ${nextDay.epoch + 1}:`,
      ARRIVES,
    );
    await expect(entry(/\(later\/fan_later\): cancelled: the run started over$/)).toHaveCount(
      1,
      ARRIVES,
    );
    await expect(entries).toHaveCount(1);
    const started = (await (await page.request.post(`${PLAYBACK}/pause`)).json()) as {
      commands: unknown[];
      targets: unknown[];
      crop: unknown[];
    };
    expect([started.commands, started.targets, started.crop]).toEqual([[], [], []]);
  });
});
