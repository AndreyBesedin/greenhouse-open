import { expect, type Page, type Route, test } from "@playwright/test";

async function openLive(page: Page): Promise<void> {
  await page.goto("/?live=climate_box");
  await expect(page.getByRole("button", { name: "Pause", exact: true })).toBeEnabled();
}

async function holdCommand(page: Page, command: string): Promise<{ received: Promise<Route> }> {
  let receive: (route: Route) => void = () => undefined;
  const received = new Promise<Route>((resolve) => {
    receive = resolve;
  });
  await page.route(`**/api/scenarios/climate_box/live/${command}`, (route) => receive(route));
  return { received };
}

async function answer(page: Page, route: Route, problem: string | null): Promise<void> {
  // Wait until the browser has consumed the result before asserting absence.
  const response = page.waitForResponse(route.request().url());
  await route.fulfill({
    status: problem === null ? 200 : 400,
    json: problem === null ? {} : { error: problem },
  });
  await (await response).finished();
  // A round trip through another UI event also flushes the command's update.
  await page.getByRole("button", { name: "Top", exact: true }).click();
}

for (const returnToOriginal of [false, true]) {
  test(`a delayed command cannot affect a different source${returnToOriginal ? ", even after returning" : ""}`, async ({
    page,
  }) => {
    const pending = await holdCommand(page, "pause");
    await openLive(page);
    await page.getByRole("button", { name: "Pause", exact: true }).click();
    const route = await pending.received;

    await page.getByRole("button", { name: "Play airflow_box live", exact: true }).click();
    await expect(page.getByTestId("scene-status")).toContainText(
      "scenario airflow_box, live: airflow_box",
    );
    if (returnToOriginal) {
      await page.getByRole("button", { name: "Play climate_box live", exact: true }).click();
      await expect(page.getByTestId("scene-status")).toContainText(
        "scenario climate_box, live: climate_box",
      );
    }

    await answer(page, route, "obsolete failure");
    await expect(page.getByTestId("command-problem")).toHaveCount(0);
  });
}

for (const olderProblem of [null, "older failure"]) {
  test(`an older ${olderProblem === null ? "success" : "failure"} cannot overwrite the latest command feedback`, async ({
    page,
  }) => {
    const pending = await holdCommand(page, "pause");
    await page.route("**/api/scenarios/climate_box/live/reset", (route) =>
      route.fulfill({ status: 400, json: { error: "latest failure" } }),
    );
    await openLive(page);
    await page.getByRole("button", { name: "Pause", exact: true }).click();
    const route = await pending.received;
    await page.getByRole("button", { name: "Reset", exact: true }).click();
    await expect(page.getByTestId("command-problem")).toContainText("latest failure");

    await answer(page, route, olderProblem);
    await expect(page.getByTestId("command-problem")).toContainText("latest failure");
  });
}
