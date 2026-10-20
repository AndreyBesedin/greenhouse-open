import { expect, type Page } from "@playwright/test";

/** The panels folded to the line that says how they stand (#206), by the
 * name of the group of controls each holds. */
const FOLDS = {
  Equipment: "equipment-fold",
  Openings: "openings-fold",
  Probes: "probes-fold",
} as const;

/** Unfolds a panel folded to its line (#206), unless it is open already;
 * it stays open while the page does. */
export async function unfold(page: Page, name: keyof typeof FOLDS): Promise<void> {
  const details = page.locator(`details.${FOLDS[name]}`);
  if ((await details.getAttribute("open")) === null) {
    await details.locator(":scope > summary").click();
  }
  await expect(details).toHaveAttribute("open");
}
