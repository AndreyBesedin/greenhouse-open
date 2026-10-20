import { expect, type Page, test } from "@playwright/test";
import { chooser } from "./chooser";
import { selectAt } from "./view";

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

  await (await chooser(page)).getByRole("button", { name: "Open tomato_compartment" }).click();

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

test("the reference greenhouse, the example scene, and Back to the greenhouse as it was (#201)", async ({
  page,
}) => {
  const errors = collectErrors(page);
  const status = page.getByTestId("scene-status");
  const greenhouse =
    "Showing the scenario reference_greenhouse, before day one: reference_greenhouse";
  const example = "Showing the example scene: climate_box, day 9, 128 entities.";
  await page.goto("/?scenario=reference_greenhouse&weather=default~90");
  await expect(status).toContainText(greenhouse);
  // Chosen, a scenario's view starts with the choice folded to its line.
  await expect(page.locator("details.source-chooser")).not.toHaveAttribute("open");

  await test.step("another scene is a new page, and the choice folds once made", async () => {
    await (await chooser(page)).getByRole("button", { name: "Example scene" }).click();
    await expect(status).toHaveText(example);
    await expect(page).toHaveURL(/\?scene=example$/);
    await expect(page.locator("details.source-chooser")).not.toHaveAttribute("open");
  });

  await test.step("Back returns to the greenhouse, as its address held it", async () => {
    await page.goBack();
    await expect(page).toHaveURL(/\?scenario=reference_greenhouse&weather=default~90$/);
    await expect(status).toContainText(greenhouse);
  });

  await test.step("and Forward to the example scene again", async () => {
    await page.goForward();
    await expect(status).toHaveText(example);
    await (await chooser(page)).getByRole("button", { name: "Empty grid" }).click();
    await expect(status).toHaveText("Showing the empty grid.");
    await page.goBack();
    await expect(status).toHaveText(example);
  });
  expect(errors).toEqual([]);
});

test("Back and Forward start a view afresh, as a choice of it does (#201)", async ({ page }) => {
  // A plant of the climate box, by the default camera; the example scene is
  // the climate box too, its plants named alike.
  const plant = { x: 2.25, y: 2.4, z: 0.775 };
  const status = page.getByTestId("scene-status");
  await page.goto("/?scenario=climate_box");
  await expect(status).toContainText("climate_box, day 0, 128 entities");
  await (await chooser(page)).getByRole("button", { name: "Example scene" }).click();
  await expect(status).toContainText("Showing the example scene");

  await page.goBack();
  await expect(status).toContainText("Showing the scenario climate_box");
  await selectAt(page, plant, "climate_box_plant_001");
  await page.getByLabel("Colour by").selectOption("age_days");

  await page.goForward();
  await expect(status).toContainText("Showing the example scene");
  await expect(page.getByTestId("selected-entity")).toHaveCount(0);
  await expect(page.getByLabel("Colour by")).toHaveValue("");
});
