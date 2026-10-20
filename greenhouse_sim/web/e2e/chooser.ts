import { expect, type Locator, type Page } from "@playwright/test";

/** The choice of what the viewer shows (#201), opened: it is open at the
 * bare address, and folds once a choice is made, so each choice opens it. */
export async function chooser(page: Page): Promise<Locator> {
  const details = page.locator("details.source-chooser");
  if ((await details.getAttribute("open")) === null) {
    await details.locator(":scope > summary").click();
  }
  await expect(details).toHaveAttribute("open");
  return details;
}

/** A scenario's layout picker, in the chooser, opened. */
export async function layoutPicker(page: Page, scenarioId: string): Promise<Locator> {
  return (await chooser(page)).getByRole("combobox", { name: `Layout of ${scenarioId}` });
}
