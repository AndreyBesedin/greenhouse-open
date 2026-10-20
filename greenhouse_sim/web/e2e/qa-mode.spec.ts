import { expect, test } from "@playwright/test";

import type { CameraPose } from "../src/camera.ts";
import { cameraText } from "./cameraView";
import { selectAt } from "./view";

// P09.6: QA mode, off by default, is the only way the viewer asks for what
// the simulator knows and a policy never sees.

// The climate box's front temperature sensor, which is clean, ten minutes
// into a heated run; a point on its face, seen from 1.5 m beside it.
const FRONT_FACE = { x: 3.04, y: 3.1, z: 1.5 };
const BESIDE_THE_FRONT: CameraPose = {
  position: { x: 4.5, y: 3.1, z: 1.7 },
  target: FRONT_FACE,
};
const HEATED_RUN = `/?scenario=climate_box&set=heater:1&field=climate&t=600&camera=${cameraText(BESIDE_THE_FRONT)}`;
const TRUTH = /\/climate\/truth(\?|$)/;

test("QA mode: no truth is asked for without it, and turning it on shows the truth", async ({
  page,
}) => {
  const truthAsked: string[] = [];
  page.on("request", (request) => {
    if (TRUTH.test(new URL(request.url()).pathname)) {
      truthAsked.push(request.url());
    }
  });
  await page.goto(HEATED_RUN);
  await expect(page.getByTestId("climate-time")).toHaveText("10 min", { timeout: 20_000 });
  const qaMode = page.getByRole("checkbox", { name: "QA mode" });
  await expect(qaMode).not.toBeChecked();

  await selectAt(page, FRONT_FACE, "climate_box_temperature_front", BESIDE_THE_FRONT);
  const panel = page.getByRole("region", { name: "Sensor" });
  await expect(panel.getByTestId("sensor-reading")).toHaveText("15.91 °C at 10 min", {
    timeout: 20_000,
  });
  // Its readings alone: no truth, no line of it, no switch to clean them.
  await expect(panel.locator(".sensor-chart-reading")).toHaveCount(11);
  await expect(panel.getByTestId("sensor-chart-truth")).toHaveCount(0);
  await expect(panel.getByRole("complementary", { name: "Truth, for QA only" })).toHaveCount(0);
  await expect(panel.getByRole("checkbox", { name: "Imperfections" })).toHaveCount(0);
  expect(truthAsked).toEqual([]);

  // Turned on, the address keeps it, and the truth is asked for and shown.
  const asked = page.waitForRequest((request) => TRUTH.test(new URL(request.url()).pathname));
  await qaMode.check();
  await expect(page).toHaveURL(/&qa=1$/);
  await asked;
  await expect(panel.getByTestId("sensor-truth")).toHaveText("15.91 °C at 10 min", {
    timeout: 20_000,
  });
  await expect(panel.getByTestId("sensor-chart-truth")).toHaveCount(1);

  // Turned off again, the truth goes, and the address forgets it.
  await qaMode.uncheck();
  await expect(page).not.toHaveURL(/qa=1/);
  await expect(panel.getByRole("complementary", { name: "Truth, for QA only" })).toHaveCount(0);
  await expect(panel.getByTestId("sensor-reading")).toHaveText("15.91 °C at 10 min");
});

test("QA mode: every plant is labelled with its identifier and its day's light", async ({
  page,
}) => {
  await page.goto("/?scenario=climate_box&field=climate&t=600");
  await expect(page.getByTestId("climate-time")).toHaveText("10 min", { timeout: 20_000 });
  const labels = page.getByTestId("debug-label");
  await expect(labels).toHaveCount(0);

  await page.getByRole("checkbox", { name: "QA mode" }).check();
  const plantLabels = labels.filter({ hasText: /^climate_box_plant_\d{3} / });
  await expect(plantLabels).toHaveCount(32, { timeout: 20_000 });
  await expect(labels.filter({ hasText: /^climate_box_plant_001 / })).toHaveText(
    /^climate_box_plant_001 \d+\.\d mol\/m²\/d$/,
  );
});

test("QA mode: a probe's label says what the field drawn holds there", async ({ page }) => {
  // The P04 airflow QA case's probes (probes.spec.ts), upstream of its block
  // and in its wake, as OpenFOAM solved it, drawn as arrows: the air's speed.
  await page.goto("/?scenario=airflow_box&field=cfd&probes=3:3.2:0.75,7:3.2:0.75&qa=1");
  await expect(page.getByRole("checkbox", { name: "QA mode" })).toBeChecked();
  await expect(page.getByTestId("debug-label").filter({ hasText: /^P\d/ })).toHaveText([
    "P1 0.43 m/s",
    "P2 0.02 m/s",
  ]);
  // Its one plant is labelled too; outside a climate run, without its light.
  await expect(page.getByTestId("debug-label").filter({ hasText: /plant/ })).toHaveText([
    "airflow_box_plant_001",
  ]);
});

test("QA mode: the run's manifest says what it is made from, and the versions served", async ({
  page,
}) => {
  await page.goto("/?scenario=climate_box&weather=cold_spring_day&clouds=80&qa=1");
  const panel = page.getByRole("region", { name: "QA mode" });
  await expect(panel.getByTestId("manifest-scenario")).toHaveText(
    /^climate_box, version [0-9a-f]{16}, format 2$/,
  );
  await expect(panel.getByTestId("manifest-seed")).toHaveText("1201");
  await expect(panel.getByTestId("manifest-season")).toHaveText("from 2026-01-01, 14 days");
  await expect(panel.getByTestId("manifest-crop")).toHaveText(
    "cherry_tomato, the simple daily model",
  );
  await expect(panel.getByTestId("manifest-weather")).toHaveText(
    "cold_spring_day, synthetic, clouds 80%",
  );

  // The simulator's version and commit as the API serves them, and the
  // viewer's as it was built; warned of only if both commits are known and
  // differ. A simulator installed as a package, as CI installs it, does not
  // know its commit.
  const served = (await (await page.request.get("/api/version")).json()) as {
    version: string;
    commit: string;
  };
  expect(served.commit).toMatch(/^([0-9a-f]{7,}|unknown)$/);
  await expect(panel.getByTestId("manifest-simulator")).toHaveText(
    `${served.version}, commit ${served.commit}`,
  );
  // The viewer's commit, as the info panel's last line says it.
  const built = (await page.getByTestId("build-line").textContent())?.match(/commit (\S+)$/)?.[1];
  await expect(panel.getByTestId("manifest-viewer")).toHaveText(
    `${served.version}, commit ${built}`,
  );
  const known = served.commit !== "unknown" && built !== "unknown";
  await expect(panel.getByTestId("manifest-commits-differ")).toHaveCount(
    known && built !== served.commit ? 1 : 0,
  );

  // Out of QA mode, no panel.
  await page.getByRole("checkbox", { name: "QA mode" }).uncheck();
  await expect(panel).toHaveCount(0);
});

test("QA mode: the developer panel says what each process holds at the moment", async ({
  page,
}) => {
  // Twenty minutes into the heated run, the back sensor's sample at 19 min
  // has dropped out (sensors.spec.ts): it is stale until the next comes.
  await page.goto("/?scenario=climate_box&set=heater:1&field=climate&t=1200&qa=1");
  await expect(page.getByTestId("climate-time")).toHaveText("20 min", { timeout: 20_000 });
  const panel = page.getByRole("region", { name: "QA mode" });
  await expect(panel.getByTestId("developer-clock")).toHaveText(
    /^20 min \(2025-12-31 23:20 UTC\), run climate_box-climate-[0-9a-f]{8}$/,
    { timeout: 20_000 },
  );
  await expect(panel.getByTestId("developer-house-air")).toHaveText(
    /^\d+(\.\d+)? °C, \d+(\.\d+)?%, 420 ppm$/,
  );
  await expect(panel.getByTestId("developer-crop")).toHaveText(
    "32 plants, the simple daily model; no day lived yet",
  );
  await expect(panel.getByTestId("developer-levels")).toContainText("heater 100%");
  await expect(panel.getByTestId("developer-commands")).toContainText("1 given, the latest:");
  await expect(panel.getByTestId("developer-latest-commands")).toHaveText("0 min: heater 100%");
  const stale = panel.getByTestId("developer-sensors").locator("li.stale");
  await expect(stale).toHaveText(["temperature_back: stale, latest 18 min"]);
  // A frame a minute from the start.
  await expect(panel.getByTestId("developer-cameras")).toHaveText(
    "front_camera: 21 frames, latest 20 min",
  );

  // A minute on, its reading has come.
  await page.getByRole("slider", { name: "Time of day" }).fill("1260");
  await expect(panel.getByTestId("developer-clock")).toHaveText(/^21 min /, { timeout: 20_000 });
  await expect(stale).toHaveCount(0);
  await expect(panel.getByTestId("developer-cameras")).toHaveText(
    "front_camera: 22 frames, latest 21 min",
  );
});
