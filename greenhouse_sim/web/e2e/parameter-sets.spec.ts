import { readFileSync } from "node:fs";

import { expect, type Locator, test } from "@playwright/test";

import { lowContrast } from "./contrast.ts";

// A crop parameter set edited in the setup builder, beside the rows (P20.5): a
// new version drawn from the schema of its model's parameters, each with its
// unit, range and source, a fixed one read only; a value outside its range
// refused by its field; then saved as a version, compared with its base and
// downloaded as its file. The simulator served keeps the sets in a run store of
// the test run's own.

// On CI the simulator may still be working out what the spec before this one
// asked for.
const ARRIVES = { timeout: 60_000 };
// A compact control's least height and width (`--target-compact`, P19.9).
const COMPACT_TARGET_PX = 24;
const CONTROLS = "button, select, input";

/** Each of `controls` smaller than a compact target, by its name. */
async function tooSmall(controls: Locator): Promise<string[]> {
  const small: string[] = [];
  for (const control of await controls.all()) {
    const box = await control.boundingBox();
    if ((box?.height ?? 0) < COMPACT_TARGET_PX || (box?.width ?? 0) < COMPACT_TARGET_PX) {
      small.push(
        `${await control.evaluate((element) => element.id)}: ${box?.width} by ${box?.height}`,
      );
    }
  }
  return small;
}

test("builder: a crop parameter set edited, refused outside its range, saved, compared and downloaded", async ({
  page,
}) => {
  test.setTimeout(120_000);
  // A name of its own, so that a retry against the same simulator saves its
  // own first version.
  const stamp = Date.now();
  const name = `e2e_brighter_${stamp}`;

  await page.goto("/builder");
  const house = page.getByRole("form", { name: "A new house", exact: true });
  await house.getByLabel("Identifier", { exact: true }).fill(`e2e_sets_${stamp}`);
  await house.getByLabel("Crop model", { exact: true }).selectOption("reduced_tomgro");
  await house.getByRole("button", { name: "Draft this house" }).click();
  await expect(page.getByTestId("builder-status")).toContainText("Drafted", ARRIVES);

  // The rows grow Reduced-State TOMGRO: its published set is chosen first.
  const sets = page.getByRole("region", { name: "Crop parameters", exact: true });
  await expect(sets.getByLabel("Parameter set", { exact: true })).toHaveValue("gnvman v1", ARRIVES);
  await expect(sets.getByTestId("parameter-set-chosen")).toContainText(
    "Its model's published set, made for reduced_tomgro version 1. Its digest is sha256:",
  );
  await expect(sets.getByRole("button", { name: "Compare with its base" })).toBeDisabled();

  // A new version, folded until opened, each parameter as the model's schema
  // describes it: what it is, its unit and range, and its source.
  await sets.getByText("A new version, based on gnvman v1", { exact: true }).click();
  const form = sets.getByRole("form");
  const alphaLabel = /^alpha_F: the share of the day's net growth/;
  const alpha = form.getByLabel(alphaLabel);
  await expect(alpha).toHaveValue("0.8");
  await expect(alpha).toHaveAccessibleDescription("In fraction d⁻¹, from 0 to 1.");
  const alphaBlock = form
    .locator(".builder-parameter")
    .filter({ has: page.getByLabel(alphaLabel) });
  await alphaBlock.getByText("Where it comes from", { exact: true }).click();
  await expect(alphaBlock).toContainText("Oliveira et al. v0.4.0");
  await expect(alphaBlock).toContainText("Its most, 1: a share, of all of it at most");
  // A fixed parameter is read only, and says why.
  const conversion = form.getByLabel(/^D, an input: the conversion/);
  await expect(conversion).not.toBeEditable();
  await expect(conversion).toHaveAccessibleDescription(
    "In g CH₂O s d⁻¹ µmol⁻¹ CO₂. Fixed: a conversion of units: no set changes it.",
  );
  // Its controls are targets, its words stand out from what they are drawn on.
  expect(await tooSmall(sets.locator(CONTROLS))).toEqual([]);
  expect(await lowContrast(sets)).toEqual([]);

  // Outside its range: the simulator refuses it, by its field, and keeps nothing.
  await form.getByLabel("Name", { exact: true }).fill(name);
  await alpha.fill("2");
  await form.getByLabel("Why alpha_f", { exact: true }).fill("a browser test's");
  await form.getByRole("button", { name: "Save this version" }).click();
  await expect(sets.getByTestId("parameter-set-problem")).toHaveText(
    "Not saved: parameters.alpha_f: Input should be less than or equal to 1",
    ARRIVES,
  );
  await expect(alpha).toHaveAttribute("aria-invalid", "true");
  await expect(alpha).toHaveAccessibleDescription(
    "In fraction d⁻¹, from 0 to 1. Input should be less than or equal to 1",
  );
  await expect(sets.getByLabel("Parameter set", { exact: true }).locator("option")).toHaveText([
    "gnvman v1, published",
  ]);
  // Within it: saved as its name's first version, which is then chosen.
  await alpha.fill("0.7");
  await form.getByRole("button", { name: "Save this version" }).click();
  await expect(sets.getByTestId("parameter-set-status")).toHaveText(
    new RegExp(`^Saved as ${name} v1, sha256:[0-9a-f]{64}\\.$`),
    ARRIVES,
  );
  await expect(sets.getByTestId("parameter-set-problem")).toHaveCount(0);
  await expect(sets.getByLabel("Parameter set", { exact: true })).toHaveValue(`${name} v1`);
  await expect(sets.getByTestId("parameter-set-chosen")).toContainText("Based on gnvman v1");

  // Compared with its base: the one value it changes.
  await sets.getByRole("button", { name: "Compare with its base" }).click();
  const comparison = sets.getByRole("table");
  await expect(comparison).toContainText(
    `${name} v1 against its base, gnvman v1: 1 parameter differs`,
    ARRIVES,
  );
  await expect(comparison.getByRole("rowheader")).toHaveText(["alpha_f"]);
  await expect(comparison.locator("tbody td")).toHaveText(["0.8", "0.7"]);
  // Downloaded, as the simulator writes its file.
  const downloading = page.waitForEvent("download");
  await sets.getByRole("button", { name: "Download its file" }).click();
  const download = await downloading;
  expect(download.suggestedFilename()).toBe(`reduced_tomgro.${name}.v1.parameter_set.json`);
  expect(JSON.parse(readFileSync(await download.path(), "utf8"))).toMatchObject({
    model: "reduced_tomgro",
    name,
    version: 1,
    based_on: { name: "gnvman", version: 1 },
    parameters: { alpha_f: 0.7 },
    why: { alpha_f: "a browser test's" },
  });
});
