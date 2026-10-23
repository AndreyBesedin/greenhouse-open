import { expect, test } from "@playwright/test";

import { FOLDS, type FoldName, unfold } from "./folds";

// A scenario followed, as the scenarios table opens one (#245): the run
// played back, its moment, and every group of the info panel beside them.
const FOLLOWED = "/?scenario=climate_box&field=climate&follow=1";
// The info panel's sections, by their names in `folds.ts`, folded at first
// but the climate run's moment (#273).
const FOLDED: readonly FoldName[] = [
  "Display",
  "Air field",
  "House air",
  "Weather",
  "Probes",
  "Openings",
  "Equipment",
];
const OPEN: readonly FoldName[] = ["Climate run"];
// Two controls closer than this, in pixels, touch.
const LEAST_GAP_PX = 2;

interface Box {
  name: string;
  left: number;
  right: number;
  top: number;
  bottom: number;
}

/** How far apart two boxes are: across, if they share a row, or else down;
 * negative if they overlap. */
function apart(a: Box, b: Box): number {
  const across = Math.max(a.left, b.left) - Math.min(a.right, b.right);
  const down = Math.max(a.top, b.top) - Math.min(a.bottom, b.bottom);
  return Math.max(across, down);
}

test("info panel: every group a section folded to its line, the panel fitting a small window, no two controls touching (#273)", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto(FOLLOWED);
  const panel = page.locator(".info-panel");
  await expect(page.getByRole("region", { name: "Run played back" })).toBeVisible({
    timeout: 20_000,
  });
  await expect(page.getByTestId("climate-time")).toBeVisible({ timeout: 20_000 });

  await test.step("folded at first but the moment, the panel fits without scrolling", async () => {
    for (const name of FOLDED) {
      await expect(panel.locator(`details.${FOLDS[name]}`)).not.toHaveAttribute("open");
    }
    for (const name of OPEN) {
      await expect(panel.locator(`details.${FOLDS[name]}`)).toHaveAttribute("open");
    }
    const scrolls = await panel.evaluate((element) => element.scrollHeight > element.clientHeight);
    expect(scrolls).toBe(false);
    await expect(page.getByRole("button", { name: "Stop following" })).toBeInViewport();
    await expect(page.getByRole("group", { name: "Climate run" })).toBeInViewport();
  });

  await test.step("each section opens by its line, and no two controls touch", async () => {
    for (const name of FOLDED) {
      await unfold(page, name);
    }
    const boxes: Box[] = await panel.evaluate((element) =>
      [...element.querySelectorAll("button, select, input, summary")]
        // Drawn: a closed section's controls keep a box, but are not shown.
        .filter((control) =>
          control.checkVisibility({ contentVisibilityAuto: true, visibilityProperty: true }),
        )
        .map((control) => {
          const box = control.getBoundingClientRect();
          const name =
            control.getAttribute("aria-label") ??
            control.textContent?.trim().slice(0, 40) ??
            control.tagName;
          return { name, left: box.left, right: box.right, top: box.top, bottom: box.bottom };
        })
        .filter((box) => box.right > box.left && box.bottom > box.top),
    );
    expect(boxes.length).toBeGreaterThan(20);
    const touching = boxes.flatMap((a, i) =>
      boxes
        .slice(i + 1)
        .filter((b) => apart(a, b) < LEAST_GAP_PX)
        .map((b) => `${a.name} / ${b.name}: ${apart(a, b).toFixed(1)} px`),
    );
    expect(touching).toEqual([]);
  });
});

test("info panel: the sections sit in titled cards by topic (#306)", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await page.goto(FOLLOWED);
  await expect(page.getByTestId("climate-time")).toBeVisible({ timeout: 20_000 });
  const panel = page.locator(".info-panel");
  const card = (title: string) => panel.getByRole("region", { name: title, exact: true });

  await expect(panel.locator(".panel-card-title")).toHaveText([
    "Simulation",
    "House",
    "Equipment",
    "Outside",
  ]);
  await expect(card("Simulation").getByRole("region", { name: "Run played back" })).toBeVisible();
  await expect(card("Simulation").locator("details.moment-fold")).toBeVisible();
  await expect(card("Simulation").locator("details.timeline")).toBeVisible();
  await expect(card("Simulation").locator("details.checkpoints")).toBeVisible();
  await expect(card("House").locator("details.field-fold")).toBeVisible();
  await expect(card("House").locator("details.house-fold")).toBeVisible();
  await expect(card("Equipment").locator("details.probes-fold")).toBeVisible();
  await expect(card("Equipment").locator("details.openings-fold")).toBeVisible();
  await expect(card("Equipment").locator("details.equipment-fold")).toBeVisible();
  await expect(card("Outside").getByRole("region", { name: "Weather" })).toBeVisible();
});

test("info panel: a card with nothing in it is not drawn (#306)", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  // The sensor lab has no equipment and no openings, nothing is probed, and
  // no run is played back or worked out.
  await page.goto("/?scenario=sensor_lab");
  await expect(page.getByTestId("scene-status")).toContainText("sensor_lab, day 0", {
    timeout: 20_000,
  });
  const panel = page.locator(".info-panel");
  await expect(panel.getByRole("region", { name: "Weather" })).toBeVisible();

  await expect(panel.locator(".panel-card-title")).toHaveText(["House", "Outside"]);
});
