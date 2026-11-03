import { existsSync } from "node:fs";

import { expect, type Page, test } from "@playwright/test";

import { BUILDER_PATH, LANDING_PATH, replayAddress, runsAddress } from "../../src/landing/paths.ts";
import type { PanelTheme } from "../../src/panelTheme.ts";
import { answerAsTheSimulator, DRAWN_AT, EPOCH, RUN_ID, SCENARIO_ID } from "./pageAnswers.ts";

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
// Where a person's choice of theme is kept (`panelTheme.ts`).
const STORED_THEME = "greenhouse-sim.panels";
const THEMES: readonly PanelTheme[] = ["dark", "light"];
// How long a comparison that should fail keeps looking for a match.
const FAILS_WITHIN_MS = 3000;

interface Drawn {
  name: string;
  address: string;
  /** Waits until the page shows what its baseline holds. */
  shown: (page: Page) => Promise<void>;
}

const PAGES: readonly Drawn[] = [
  {
    name: "landing",
    address: LANDING_PATH,
    shown: async (page) => {
      await expect(page.getByRole("heading", { name: "What would you like to do?" })).toBeVisible();
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
];

async function open(page: Page, drawn: Drawn, theme: PanelTheme): Promise<string[]> {
  // Dates and their words are the same on every run, and every machine.
  await page.clock.setFixedTime(new Date(DRAWN_AT));
  await page.addInitScript(
    ([key, value]) => localStorage.setItem(key as string, value as string),
    [STORED_THEME, theme],
  );
  const unanswered = await answerAsTheSimulator(page);
  await page.goto(drawn.address);
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

      await expect(page).toHaveScreenshot(baseline, EXACT);
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
