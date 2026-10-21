import { expect, type Page, type Request, test } from "@playwright/test";

import type { CameraPose } from "../src/camera.ts";
import type { Point3 } from "../src/world.ts";
import { onScreen, selectAt } from "./view";

// The climate box seen from outside its right side wall, through the glass,
// as equipment.spec.ts sees it: the heater in its back right corner, its
// base at (11.2, 0.7), its box 0.6 m by 0.8 m; a point on its side facing
// the camera, and its foot below it. The dehumidifier against the back
// wall, its base at (6.0, 5.9), and a point on its front.
const ACROSS: CameraPose = {
  position: { x: 6, y: -8, z: 4 },
  target: { x: 6, y: 3.2, z: 1.2 },
};
const HEATER_SIDE = { x: 11.2, y: 0.3, z: 0.6 };
const HEATER_FOOT = { x: 11.2, y: 0.3, z: 0 };
// A metre towards the front wall and half a metre into the house.
const MOVED_FOOT = { x: 10.2, y: 0.8, z: 0 };
const MOVED_SIDE = { x: 10.2, y: 0.8, z: 0.6 };
const DEHUMIDIFIER_FRONT = { x: 6.0, y: 5.6, z: 1.3 };
const DEHUMIDIFIER_FOOT = { x: 6.0, y: 5.6, z: 0 };
// A metre towards the front wall, along the back one.
const DEHUMIDIFIER_MOVED_FOOT = { x: 5.0, y: 5.6, z: 0 };
const BOTH_MOVED = /[?&]layout=default~dehumidifier:-1:0,heater:-1:0\.5(&|$)/;
const HEATER_MOVED = /[?&]layout=default~heater:-1:0\.5(&|$)/;
const ARRIVES = { timeout: 60_000 };

function cameraText({ position, target }: CameraPose): string {
  return [position, target].map(({ x, y, z }) => `${x}:${y}:${z}`).join(",");
}

/** Drags in the view from one world point to another, as the view sees
 * them, and lets go, unless told to hold on. */
async function drag(page: Page, from: Point3, to: Point3, letGo = true): Promise<void> {
  const start = await onScreen(page, from, ACROSS);
  const end = await onScreen(page, to, ACROSS);
  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  await page.mouse.move(end.x, end.y, { steps: 10 });
  if (letGo) {
    await page.mouse.up();
  }
}

/** The layouts with moves the page asks the simulator for anything of. */
function movedLayoutsAsked(page: Page): string[] {
  const asked: string[] = [];
  page.on("request", (request: Request) => {
    const url = new URL(request.url());
    const layout = url.searchParams.get("layout") ?? "";
    if (url.pathname.startsWith("/api/") && layout.includes("~")) {
      asked.push(layout);
    }
  });
  return asked;
}

test("moving: two items moved in one session are held until applied, then make one new run, from its start (#271)", async ({
  page,
}) => {
  // Four drags and picks, and three scenes: at the few frames a second CI
  // draws, far longer than the default allows.
  test.setTimeout(180_000);
  const position = page.getByTestId("selected-position");
  const move = page.getByRole("region", { name: "Move", exact: true });
  const asked = movedLayoutsAsked(page);

  await test.step("the heater and the dehumidifier are dragged, and stay where they are dropped", async () => {
    // An hour into the run.
    await page.goto(`/?scenario=climate_box&t=3600&camera=${cameraText(ACROSS)}`);
    await expect(page.getByTestId("scene-status")).toContainText("128 entities", ARRIVES);
    await selectAt(page, HEATER_SIDE, "climate_box_heater", ACROSS);
    await move.getByRole("button", { name: "Move", exact: true }).click();
    await expect(move.getByTestId("move-new-run")).toHaveText(
      "Moving equipment changes the house's climate, so it is a new run: applying these moves starts it from its first day.",
    );

    await drag(page, HEATER_FOOT, MOVED_FOOT);
    await expect(position).toHaveText("x 10.20, y 1.20, z 0.00");
    await expect(move.getByTestId("move-offset")).toHaveText(
      "The heater stands −1.0 m along x and +0.5 m along y from where its layout places it.",
    );
    // A click picks the next item to move.
    await selectAt(page, DEHUMIDIFIER_FRONT, "climate_box_dehumidifier", ACROSS);
    await drag(page, DEHUMIDIFIER_FOOT, DEHUMIDIFIER_MOVED_FOOT);
    await expect(position).toHaveText("x 5.00, y 5.90, z 0.00");

    await expect(move.getByTestId("move-list").getByRole("listitem")).toHaveText([
      /^dehumidifier: −1\.0 m along x and 0\.0 m along y/,
      /^heater: −1\.0 m along x and \+0\.5 m along y/,
    ]);
    // Nothing is asked of the simulator, nor kept in the address.
    expect(new URL(page.url()).searchParams.get("layout")).toBeNull();
    expect(new URL(page.url()).searchParams.get("t")).toBe("3600");
    expect(asked).toEqual([]);
  });

  await test.step("applied, both moves make one new run, from its start", async () => {
    await move.getByRole("button", { name: "Start a new run with these moves" }).click();

    await expect(page).toHaveURL(BOTH_MOVED);
    expect(new URL(page.url()).searchParams.get("t")).toBeNull();
    await expect(page.getByTestId("scene-status")).toContainText("moved", ARRIVES);
    await expect(move.getByRole("button", { name: "Move", exact: true })).toBeVisible();
    await expect(position).toHaveText("x 5.00, y 5.90, z 0.00");
    // The new scene draws the heater where it was dropped.
    await selectAt(page, MOVED_SIDE, "climate_box_heater", ACROSS);
    await expect(position).toHaveText("x 10.20, y 1.20, z 0.00");
    // One run: every moved layout asked for is the one with both moves.
    expect(new Set(asked)).toEqual(new Set(["default~dehumidifier:-1:0,heater:-1:0.5"]));
  });

  await test.step("Back takes the new run back, to where the view stood", async () => {
    await page.goBack();

    await expect(page).not.toHaveURL(/layout=/);
    expect(new URL(page.url()).searchParams.get("t")).toBe("3600");
    await selectAt(page, HEATER_SIDE, "climate_box_heater", ACROSS);
    await expect(position).toHaveText("x 11.20, y 0.70, z 0.00");
  });
});

test("moving: cancel and Escape leave the room as it was, and a move in the layout moves on or back (#271)", async ({
  page,
}) => {
  test.setTimeout(180_000);
  const position = page.getByTestId("selected-position");
  const move = page.getByRole("region", { name: "Move", exact: true });
  const offset = move.getByTestId("move-offset");
  const startMoving = () => move.getByRole("button", { name: "Move", exact: true }).click();
  await page.goto(
    `/?scenario=climate_box&layout=default~heater:-1:0.5&camera=${cameraText(ACROSS)}`,
  );
  await expect(page.getByTestId("scene-status")).toContainText("heater moved", ARRIVES);
  await selectAt(page, MOVED_SIDE, "climate_box_heater", ACROSS);
  const asked = movedLayoutsAsked(page);

  await test.step("put back in the session, then cancelled", async () => {
    await startMoving();
    await move.getByRole("button", { name: "Put the heater back" }).click();
    await expect(offset).toHaveText("The heater stands where its layout places it.");
    await expect(position).toHaveText("x 11.20, y 0.70, z 0.00");
    await expect(move.getByTestId("move-list")).toHaveText(
      "Everything stands where its layout places it.",
    );

    await move.getByRole("button", { name: "Cancel" }).click();
    await expect(offset).toHaveText(
      "The heater stands −1.0 m along x and +0.5 m along y from where its layout places it.",
    );
    await expect(position).toHaveText("x 10.20, y 1.20, z 0.00");
  });

  await test.step("moved on, then Escape: a drag first, then the session", async () => {
    await startMoving();
    // Held on: Escape cancels the drag alone.
    await drag(page, MOVED_FOOT, { x: 10.5, y: 0.8, z: 0 }, false);
    await expect(offset).toContainText("−0.7 m along x");
    await page.keyboard.press("Escape");
    await page.mouse.up();
    await expect(offset).toContainText("−1.0 m along x");
    await expect(move.getByTestId("move-new-run")).toBeVisible();

    await drag(page, MOVED_FOOT, { x: 10.5, y: 0.8, z: 0 });
    await expect(offset).toHaveText(
      "The heater stands −0.7 m along x and +0.5 m along y from where its layout places it.",
    );
    await page.keyboard.press("Escape");
    await expect(move.getByTestId("move-new-run")).toHaveCount(0);
    await expect(offset).toContainText("−1.0 m along x");
    await expect(position).toHaveText("x 10.20, y 1.20, z 0.00");
  });

  // The address kept the layout it opened with, and no other was asked for.
  await expect(page).toHaveURL(HEATER_MOVED);
  expect(asked.filter((layout) => layout !== "default~heater:-1:0.5")).toEqual([]);
});

test("moving while following the run played back: applied, the playback starts over with the moves, and the view follows it from its start (#271)", async ({
  page,
}) => {
  test.setTimeout(180_000);
  // The run played back, as this test's own playback says it: on day 2 at
  // 5 h until it starts over with a layout, then that layout's run from its
  // start. The playback other tests follow is left as it is; the simulator's
  // own restart with a layout is the API's tests'.
  const own = {
    run_id: "climate_box-climate-00000000",
    layout: "default",
    epoch: 0,
    simulated_now: "2026-03-03T05:00:00Z",
    time_s: 2 * 86_400 + 5 * 3600,
    day: 2,
    playing: false,
    seconds_per_day: 10,
    worked_out_s: 3 * 86_400,
  };
  let played = own;
  const restarts: string[] = [];
  await page.route("**/api/scenarios/climate_box/playback", (route) =>
    route.fulfill({ json: played }),
  );
  await page.route("**/api/scenarios/climate_box/playback/restart*", (route) => {
    const url = new URL(route.request().url());
    restarts.push(`${route.request().method()} ${url.pathname}${url.search}`);
    played = {
      ...own,
      run_id: "climate_box-climate-11111111",
      layout: "default~heater:-1.0:0.5",
      simulated_now: "2026-03-01T00:00:00Z",
      time_s: 0,
      day: 0,
      worked_out_s: 0,
    };
    return route.fulfill({ json: played });
  });
  const move = page.getByRole("region", { name: "Move", exact: true });
  const panel = page.getByRole("region", { name: "Run played back" });

  await test.step("followed, a session says the run played back starts over with its moves", async () => {
    await page.goto(`/?scenario=climate_box&field=climate&follow=1&camera=${cameraText(ACROSS)}`);
    await expect(page.getByTestId("climate-time")).toHaveText("day 2, 5 h 00 min", ARRIVES);
    await selectAt(page, HEATER_SIDE, "climate_box_heater", ACROSS);
    await move.getByRole("button", { name: "Move", exact: true }).click();
    await expect(move.getByTestId("move-new-run")).toContainText(
      "The run played back starts over with them, and the view follows it.",
    );
    await drag(page, HEATER_FOOT, MOVED_FOOT);
    await expect(page.getByTestId("selected-position")).toHaveText("x 10.20, y 1.20, z 0.00");
    expect(new URL(page.url()).searchParams.get("layout")).toBeNull();
    expect(restarts).toEqual([]);
  });

  await test.step("applied, the playback starts over with the layout, and the view follows its new run from its start", async () => {
    await move.getByRole("button", { name: "Start a new run with these moves" }).click();

    await expect(page).toHaveURL(HEATER_MOVED);
    expect(restarts).toEqual([
      "POST /api/scenarios/climate_box/playback/restart?layout=default~heater:-1:0.5",
    ]);
    await expect(panel.getByTestId("playback-status")).toContainText(
      "Following run climate_box-climate-11111111, epoch 0",
    );
    await expect(page.getByTestId("climate-time")).toHaveText("0 min", ARRIVES);
    expect(new URL(page.url()).searchParams.get("t")).toBeNull();
    // The view draws the run played back: no other run to say.
    await expect(panel.getByTestId("playback-another-run")).toHaveCount(0);
    await expect(page.getByTestId("selected-position")).toHaveText("x 10.20, y 1.20, z 0.00");
  });
});
