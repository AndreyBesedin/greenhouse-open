import { expect, type Page } from "@playwright/test";

/** The panels folded to the line that says how they stand (#206, #273), by
 * the name of the group of controls each holds. */
export const FOLDS = {
  Display: "display-fold",
  "Air field": "field-fold",
  "Climate run": "moment-fold",
  "House air": "house-fold",
  Weather: "weather-fold",
  Equipment: "equipment-fold",
  Openings: "openings-fold",
  Probes: "probes-fold",
} as const;

export type FoldName = keyof typeof FOLDS;

/** Unfolds a panel folded to its line (#206), unless it is open already;
 * it stays open while the page does. */
export async function unfold(page: Page, name: FoldName): Promise<void> {
  const details = page.locator(`details.${FOLDS[name]}`);
  if ((await details.getAttribute("open")) === null) {
    await details.locator(":scope > summary").click();
  }
  await expect(details).toHaveAttribute("open");
}
