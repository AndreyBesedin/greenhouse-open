import { expect, type Locator, type Page } from "@playwright/test";

// How long the weather may take to be read, on a loaded runner.
const READ_TIMEOUT_MS = 20_000;

/** The weather panel, opened once the weather is read: while it is being
 * read, the panel is a line of text, and a click on it opens nothing. */
export async function openWeather(page: Page): Promise<Locator> {
  const weather = page.getByRole("region", { name: "Weather" });
  const summary = weather.getByTestId("weather-summary");
  await expect(summary).toHaveText(/^Outside at /, { timeout: READ_TIMEOUT_MS });
  await summary.click();
  return weather;
}
