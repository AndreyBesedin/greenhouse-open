import { existsSync } from "node:fs";

import { expect, type Page, test } from "@playwright/test";
import type { Theme } from "../../src/design/theme.ts";
import { BUILDER_PATH, LANDING_PATH, replayAddress, runsAddress } from "../../src/landing/paths.ts";
import { designAddress } from "../../src/qa/designPage.ts";
import {
  answerAsTheSimulator,
  DRAWN_AT,
  EPOCH,
  PANELS_REPLAY,
  RUN_ID,
  SCENARIO_ID,
} from "./pageAnswers.ts";

test.skip(process.platform !== "linux", "the baselines are drawn on Linux, in CI's container");

// The stylesheet's look of each page, to the pixel (P19.1): no tolerance, as a
// change of a style that must change nothing should fail, however small. What
// the stylesheet does not draw is left out of the comparison (`pages.css`), and
// the simulator's answers are this file's, so that a baseline depends on neither
// the machine's load nor its graphics card.
const EXACT = {
  threshold: 0,
  maxDiffPixels: 0,
  stylePath: new URL("./pages.css", import.meta.url).pathname,
};
// Where a person's choice of theme is kept (`design/theme.ts`).
const STORED_THEME = "greenhouse-sim.panels";
const THEMES: readonly Theme[] = ["dark", "light"];
// How long a comparison that should fail keeps looking for a match.
const FAILS_WITHIN_MS = 3000;

interface Drawn {
  name: string;
  address: string | ((theme: Theme) => string);
  /** Waits until the page shows what its baseline holds. */
  shown: (page: Page) => Promise<void>;
  /** Taller than the view, and compared whole. */
  fullPage?: boolean;
  /** The recorded run's replay, its scenario answered (`pageAnswers.ts`). */
  run?: boolean;
  /** What of the page is compared, if not all it shows, in a view this tall. */
  part?: { selector: string; heightPx: number };
}

const PAGES: readonly Drawn[] = [
  {
    name: "landing",
    address: LANDING_PATH,
    shown: async (page) => {
      await expect(
        page.getByRole("heading", { name: "Simulate a greenhouse's climate and crop" }),
      ).toBeVisible();
      await expect(page.getByText("Failed", { exact: true })).toBeVisible();
    },
  },
  {
    name: "runs-dialog",
    address: runsAddress(SCENARIO_ID),
    shown: async (page) => {
      await expect(page.getByRole("dialog")).toBeVisible();
      await expect(page.getByRole("dialog").getByText("Failed", { exact: true })).toBeVisible();
    },
  },
  {
    name: "builder",
    address: BUILDER_PATH,
    shown: async (page) => {
      await expect(page.getByRole("heading", { name: "Setup builder" })).toBeVisible();
      await expect(page.getByText("No draft is saved yet.")).toBeVisible();
    },
  },
  {
    name: "replay",
    address: replayAddress(RUN_ID, EPOCH),
    shown: async (page) => {
      await expect(page.getByTestId("replay-moment")).toBeVisible();
      await expect(page.getByRole("slider")).toBeVisible();
    },
  },
  {
    name: "viewer",
    address: "/view?scene=example",
    shown: async (page) => {
      await expect(page.getByTestId("scene-status")).toContainText("Showing the example scene:");
      // Its panels, opened, so that what they hold is compared too.
      await page.locator("details").evaluateAll((folds) => {
        for (const fold of folds) {
          (fold as HTMLDetailsElement).open = true;
        }
      });
      await expect(page.getByText("A house for the baselines").first()).toBeVisible();
    },
  },
  {
    // A run's panels, as a replay shows them at a moment of its run, every fold
    // open, in a view tall enough for all of them (P19.11): `/view?scene=example`
    // shows few. Its fork question open, as a level set in a replay asks it.
    name: "run-panels",
    address: replayAddress(PANELS_REPLAY.runId, PANELS_REPLAY.epoch),
    run: true,
    part: { selector: ".info-panel", heightPx: 3000 },
    shown: async (page) => {
      await expect(page.getByTestId("replay-moment")).toHaveText("Day 2, 12:00");
      await expect(page.getByTestId("moment-summary")).toHaveText("Climate run: Day 2, 12:00");
      await expect(page.getByTestId("field-summary")).toContainText("Air field: climate");
      await page.locator(".info-panel details").evaluateAll((folds) => {
        for (const fold of folds) {
          (fold as HTMLDetailsElement).open = true;
        }
      });
      await page.getByRole("checkbox", { name: "heater" }).check();
      await page.getByRole("button", { name: "Fork from here with these levels" }).click();
      await expect(page.getByTestId("fork-question")).toBeVisible();
      await expect(page.getByTestId("probes-summary")).toBeVisible();
      await expect(page.locator(".weather-day svg").first()).toBeVisible();
    },
  },
  {
    // Each token and each component, in each state: with one button focused, whose
    // ring its image draws (P19.6).
    name: "design",
    address: designAddress,
    fullPage: true,
    shown: async (page) => {
      await expect(page.getByRole("button", { name: "focused", exact: true })).toBeFocused();
    },
  },
];

async function open(page: Page, drawn: Drawn, theme: Theme): Promise<string[]> {
  // Dates and their words are the same on every run, and every machine.
  await page.clock.setFixedTime(new Date(DRAWN_AT));
  await page.addInitScript(
    ([key, value]) => localStorage.setItem(key as string, value as string),
    [STORED_THEME, theme],
  );
  if (drawn.part !== undefined) {
    await page.setViewportSize({
      width: page.viewportSize()?.width ?? 0,
      height: drawn.part.heightPx,
    });
  }
  const unanswered = await answerAsTheSimulator(page, drawn.run === true);
  await page.goto(typeof drawn.address === "string" ? drawn.address : drawn.address(theme));
  await drawn.shown(page);
  return unanswered;
}

test.use({ locale: "en-US", timezoneId: "UTC" });

for (const theme of THEMES) {
  for (const drawn of PAGES) {
    test(`the ${drawn.name} page matches its baseline, ${theme}`, async ({ page }, testInfo) => {
      const baseline = `page-${drawn.name}-${theme}.png`;
      const held = existsSync(testInfo.snapshotPath(baseline, { kind: "screenshot" }));
      const unanswered = await open(page, drawn, theme);

      if (drawn.part === undefined) {
        await expect(page).toHaveScreenshot(baseline, {
          ...EXACT,
          fullPage: drawn.fullPage === true,
        });
      } else {
        await expect(page.locator(drawn.part.selector)).toHaveScreenshot(baseline, {
          ...EXACT,
          stylePath: [EXACT.stylePath, new URL("./runPanels.css", import.meta.url).pathname],
        });
      }
      expect(unanswered).toEqual([]);
      // A missing baseline is written, and that comparison passes: this fails it,
      // which keeps what was drawn for CI's `visual-results`.
      expect(held, `${baseline} is not committed: take it from visual-results`).toBe(true);
    });
  }
}

/** The colour `property` of `selector` shows, one level of blue away. */
async function oneLevelAway(page: Page, selector: string, property: string): Promise<string> {
  const [red, green, blue] = await page
    .locator(selector)
    .first()
    .evaluate(
      (element, name) =>
        (getComputedStyle(element).getPropertyValue(name).match(/\d+/g) ?? []).map(Number),
      property,
    );
  const moved = (blue ?? 0) === 0 ? 1 : (blue ?? 0) - 1;
  return `rgb(${red ?? 0} ${green ?? 0} ${moved})`;
}

// What these baselines are for: each smallest change of a style fails them. So
// that the proof cannot pass for a page drawn wrong, each compares with the same
// baseline as the test above, and each is undone by a page of its own.
test.describe("a baseline at no tolerance", () => {
  const landing = PAGES[0] as Drawn;
  const baseline = `page-${landing.name}-dark.png`;
  const changes: readonly (readonly [string, (page: Page) => Promise<string>])[] = [
    [
      "a heading's colour, one level",
      async (page) => `h1 { color: ${await oneLevelAway(page, "h1", "color")} !important; }`,
    ],
    [
      "a card's ground, one level",
      async (page) =>
        `section, section > * { background-color: ${await oneLevelAway(page, ".landing", "background-color")} !important; }`,
    ],
    ["a padding, one pixel", async () => "header { padding-left: 33px !important; }"],
    ["a radius, one pixel", async () => "button, a { border-radius: 7px !important; }"],
    ["a font size, one pixel", async () => "h1 { font-size: 19px !important; }"],
  ];

  for (const [name, written] of changes) {
    test(`fails on ${name}`, async ({ page }, testInfo) => {
      // This test only compares with the baseline: it must never be the one to write it.
      const updating = ["all", "changed"].includes(testInfo.config.updateSnapshots);
      const missing = !existsSync(testInfo.snapshotPath(baseline, { kind: "screenshot" }));
      test.skip(updating || missing, "compares with the baseline, which it must never write");

      await open(page, landing, "dark");
      await page.addStyleTag({ content: await written(page) });
      const matched = await expect(page)
        .toHaveScreenshot(baseline, { ...EXACT, timeout: FAILS_WITHIN_MS })
        .then(
          () => true,
          () => false,
        );

      expect(matched, `${name} should not match the baseline`).toBe(false);
    });
  }
});

// And what the reference page's baselines are for: a token that changes, though no
// page may show it, fails them, in its theme.
test.describe("the reference page's baseline at no tolerance", () => {
  const design = PAGES.find((drawn) => drawn.name === "design") as Drawn;
  const changes: readonly (readonly [string, Theme, string])[] = [
    ["a colour one level", "dark", ":root { --warn: #ffb37f !important; }"],
    ["a colour one level", "light", ':root[data-theme="light"] { --warn: #8a3b11 !important; }'],
    ["a colour of a chart one level", "dark", ":root { --data-sky: #2e86c0 !important; }"],
    ["a size one pixel", "dark", ":root { --space-4: 9px !important; }"],
  ];

  for (const [name, theme, written] of changes) {
    test(`fails on ${name}, ${theme}`, async ({ page }, testInfo) => {
      const baseline = `page-${design.name}-${theme}.png`;
      const updating = ["all", "changed"].includes(testInfo.config.updateSnapshots);
      const missing = !existsSync(testInfo.snapshotPath(baseline, { kind: "screenshot" }));
      test.skip(updating || missing, "compares with the baseline, which it must never write");

      await open(page, design, theme);
      await page.addStyleTag({ content: written });
      const matched = await expect(page)
        .toHaveScreenshot(baseline, { ...EXACT, fullPage: true, timeout: FAILS_WITHIN_MS })
        .then(
          () => true,
          () => false,
        );

      expect(matched, `${name} should not match the baseline`).toBe(false);
    });
  }
});
