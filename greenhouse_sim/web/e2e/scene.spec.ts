import { expect, type Page, test } from "@playwright/test";

function collectErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => {
    errors.push(error.message);
  });
  return errors;
}

async function objectCount(page: Page): Promise<number> {
  const counter = page.getByTestId("object-count");
  await expect(counter).toHaveText(/^\d+$/);
  return Number(await counter.textContent());
}

test("the example scene is drawn from its JSON file", async ({ page }) => {
  const errors = collectErrors(page);
  await page.goto("/");
  const referenceObjects = await objectCount(page);

  await page.goto("/?scene=example");

  await expect(page.getByTestId("scene-status")).toHaveText(
    "Showing the example scene: climate_box, day 9, 128 entities.",
  );
  await expect.poll(() => objectCount(page)).toBeGreaterThan(referenceObjects);
  expect(errors).toEqual([]);
});

test("a scenario's scene comes from the simulator and stays chosen on refresh", async ({
  page,
}) => {
  const errors = collectErrors(page);
  await page.goto("/");

  await page.getByRole("button", { name: "Show tomato_compartment" }).click();

  const status = page.getByTestId("scene-status");
  await expect(status).toHaveText(
    "Showing the scenario tomato_compartment, before day one: tomato_compartment, day 0, 896 entities.",
  );
  await expect(page).toHaveURL(/\?scenario=tomato_compartment$/);
  await page.reload();
  await expect(status).toHaveText(
    "Showing the scenario tomato_compartment, before day one: tomato_compartment, day 0, 896 entities.",
  );
  expect(errors).toEqual([]);
});

test("a scene with a kind the viewer does not know is refused visibly", async ({ page }) => {
  await page.route("**/api/scenarios/climate_box/scene", async (route) => {
    const response = await route.fetch();
    const scene = await response.json();
    scene.entities[0].kind = "TREE";
    await route.fulfill({ response, json: scene });
  });

  await page.goto("/?scenario=climate_box");

  const status = page.getByTestId("scene-status");
  await expect(status).toContainText("was rejected");
  await expect(status).toContainText("/entities/0/kind must be equal to one of the allowed values");
});
