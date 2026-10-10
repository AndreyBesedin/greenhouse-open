import { expect, type Locator, type Page, test } from "@playwright/test";

import type { CameraPose } from "../src/camera.ts";
import { selectAt } from "./view";

/**
 * P08's final QA, `solar-day`: the solar lab through its clear equinox day.
 * The sun crosses the sky from the east by the south to the west, and the
 * scene's light and shadows turn with it; the glass passes less light than
 * reaches it; the crates and the row of plants make their own shade; the
 * PAR on the floor follows the day; the inspector shows a plant's own PAR;
 * the day plays on; and the clouds move the light from the sun's beam to the
 * sky's.
 */

const H = 3600;
// Two probes on the floor's cells' level: in the open south of the row, and
// north of the crates, in their shade.
const IN_THE_OPEN = "5.75:1.2:0.25";
const IN_THE_SHADE = "3.05:3.9:0.25";
const LAB = `/?scenario=solar_lab&field=climate&fieldView=slice&slice=par:z:0.25&probes=${IN_THE_OPEN},${IN_THE_SHADE}`;
// The morning, the sun's noon at 4.5° east, and the evening, on the site's
// clock, and where the sun stands then.
const MOMENTS = [
  {
    name: "morning",
    seconds: 9 * H,
    shown: "9 h 00 min",
    sun: "19.3° up, at 117° (ESE)",
    from: 117,
  },
  {
    name: "noon",
    seconds: 12 * H + 50 * 60,
    shown: "12 h 50 min",
    sun: "38.0° up, at 180° (S)",
    from: 180,
  },
  {
    name: "evening",
    seconds: 16 * H + 30 * 60,
    shown: "16 h 30 min",
    sun: "20.7° up, at 241° (WSW)",
    from: 241,
  },
] as const;
const NOON = MOMENTS[1];
// The first plant, behind the crates, and the last, in the open: each picked
// by its stem, seen from the north, clear of the crates.
const SHADED_STEM = { x: 2.25, y: 3.2, z: 0.78 };
const EXPOSED_STEM = { x: 9.75, y: 3.2, z: 0.78 };
const fromTheNorth = (stem: typeof SHADED_STEM): CameraPose => ({
  position: { x: stem.x, y: 5.0, z: 0.9 },
  target: stem,
});
const ARRIVES = { timeout: 90_000 };

function cameraText({ position, target }: CameraPose): string {
  return [position, target].map(({ x, y, z }) => `${x}:${y}:${z}`).join(",");
}

async function at(page: Page, address: string, seconds: number, shown: string): Promise<void> {
  await page.goto(`${address}&t=${seconds}`);
  await expect(page.getByTestId("climate-time")).toHaveText(shown);
  await expect(page.getByTestId("field-status")).toContainText("cells", ARRIVES);
}

/** The PAR a reading or a description gives, in µmol/m²/s. */
async function parOf(locator: Locator): Promise<number> {
  const text = (await locator.textContent()) ?? "";
  const found = /PAR ([\d.]+) µmol/.exec(text);
  if (found === null) {
    throw new Error(`no PAR in ${text}`);
  }
  return Number(found[1]);
}

test("solar-day: the solar lab through its clear equinox day", async ({ page }) => {
  test.setTimeout(600_000);
  const weather = page.getByRole("region", { name: "Weather" });
  const open = page.getByTestId("probe-1-reading");
  const shade = page.getByTestId("probe-2-reading");
  const read: Record<string, { open: number; shade: number; outside: number }> = {};

  await test.step("the sun crosses the sky from the east by the south to the west, and the light turns with it", async () => {
    for (const moment of MOMENTS) {
      await at(page, LAB, moment.seconds, moment.shown);
      await weather.getByTestId("weather-summary").click();
      await expect(weather.getByTestId("weather-sun")).toHaveText(moment.sun);
      await expect(page.getByTestId("debug-label")).toContainText([`sun ${moment.sun}`]);
      // The scene is lit from where the sun stands, so its shadows fall the
      // other way.
      const view = page.getByTestId("main-view");
      await expect(view).toHaveAttribute("data-light", "sun");
      await expect(view).toHaveAttribute("data-light-from", String(moment.from));
      await expect(open).toContainText("PAR", ARRIVES);
      read[moment.name] = {
        open: await parOf(open),
        shade: await parOf(shade),
        outside: await parOf(weather.getByTestId("weather-light")),
      };
    }
  });

  await test.step("the glass passes less light than reaches it", async () => {
    for (const moment of MOMENTS) {
      const { open: inside, outside } = read[moment.name] ?? { open: 0, outside: 1 };
      // Single glass passes 85% square on, less as the beam grazes it.
      expect(inside / outside).toBeGreaterThan(0.6);
      expect(inside / outside).toBeLessThan(0.86);
    }
  });

  await test.step("the crates and the row make their own shade", async () => {
    const noon = read.noon ?? { open: 0, shade: 0 };
    // At noon the crates leave their shade only the sky's light.
    expect(noon.shade).toBeLessThan(0.25 * noon.open);
    expect(read.morning?.shade).toBeLessThan(read.morning?.open ?? 0);
  });

  await test.step("the PAR on the floor follows the day", async () => {
    expect(read.morning?.open).toBeCloseTo(483.22, 1);
    expect(read.noon?.open).toBeCloseTo(1068.75, 1);
    expect(read.evening?.open).toBeCloseTo(525.42, 1);
    await expect(page.getByTestId("field-legend-quantity")).toHaveText("PAR (µmol/m²/s)");
  });

  await test.step("the inspector shows a plant's own PAR", async () => {
    await at(
      page,
      `${LAB}&camera=${cameraText(fromTheNorth(SHADED_STEM))}`,
      NOON.seconds,
      NOON.shown,
    );
    await selectAt(page, SHADED_STEM, "solar_lab_plant_001", fromTheNorth(SHADED_STEM));
    await expect(page.getByTestId("plant-par")).toHaveText("198 µmol/m²/s", ARRIVES);
    await at(
      page,
      `${LAB}&camera=${cameraText(fromTheNorth(EXPOSED_STEM))}`,
      NOON.seconds,
      NOON.shown,
    );
    await selectAt(page, EXPOSED_STEM, "solar_lab_plant_016", fromTheNorth(EXPOSED_STEM));
    await expect(page.getByTestId("plant-par")).toHaveText("1069 µmol/m²/s", ARRIVES);
  });

  await test.step("played, the day moves on", async () => {
    await at(page, LAB, NOON.seconds - 5 * 60, "12 h 45 min");
    const run = page.getByRole("group", { name: "Climate run" });
    await run.getByRole("button", { name: "Play" }).click();
    await expect(page.getByTestId("climate-time")).toHaveText(NOON.shown, ARRIVES);
    await run.getByRole("button", { name: "Pause" }).click();
  });

  await test.step("the clouds move the light from the sun's beam to the sky's", async () => {
    await at(page, LAB, NOON.seconds, NOON.shown);
    await weather.getByTestId("weather-summary").click();
    await expect(weather.getByTestId("weather-light")).toHaveText(
      "616 W/m², 20% of it the sky's, PAR 1323 µmol/m²/s",
    );
    await weather.getByRole("slider", { name: "Cloud cover" }).fill("100");
    await expect(page).toHaveURL(/&clouds=100(&|$)/);
    await expect(weather.getByTestId("weather-light")).toHaveText(
      "154 W/m², 98% of it the sky's, PAR 331 µmol/m²/s",
      ARRIVES,
    );
    // Under a full sky of cloud the shade takes nearly what the open does.
    await expect(open).toContainText("PAR 242.95 µmol/m²/s", ARRIVES);
    await expect(shade).toContainText("PAR 238.46 µmol/m²/s", ARRIVES);
  });
});
