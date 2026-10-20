import { act } from "react";

/** The browser's Back, for tests in a DOM environment, once the page before
 * has arrived and its handlers have run. */
export async function back(): Promise<void> {
  await act(async () => {
    const arrived = new Promise((resolve) =>
      window.addEventListener("popstate", resolve, { once: true }),
    );
    history.back();
    await arrived;
  });
}
