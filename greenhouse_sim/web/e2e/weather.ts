import type { Locator, Page } from "@playwright/test";
import { expect } from "./arrives";

/** The weather panel, opened once the weather is read: while it is being
 * read, the panel is a line of text, and a click on it opens nothing. */
export async function openWeather(page: Page): Promise<Locator> {
  const weather = page.getByRole("region", { name: "Weather" });
  const summary = weather.getByTestId("weather-summary");
  await expect(summary).toHaveText(/^Outside at /);
  await summary.click();
  return weather;
}
