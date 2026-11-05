import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { BUILDER_PATH, Builder } from "./builder/Builder";
import { showTheme, storedTheme } from "./design/theme";
import { Landing } from "./landing/Landing";
import { pageAt } from "./landing/paths";
import { QA_AIRFLOW_PATH } from "./qa/airflowViews";
import { designTheme, QA_DESIGN_PATH } from "./qa/designPage";
import { QA_GREENHOUSE_PATH } from "./qa/greenhouseViews";
import { QA_LAYOUT_PATH } from "./qa/layoutViews";
import { QA_PLANTS_PATH } from "./qa/plantViews";
import { QaAirflow } from "./qa/QaAirflow";
import { QaDesign } from "./qa/QaDesign";
import { QaGreenhouse } from "./qa/QaGreenhouse";
import { QaLayout } from "./qa/QaLayout";
import { QaPlants } from "./qa/QaPlants";
import { QaReference } from "./qa/QaReference";
import { QaRenderer } from "./qa/QaRenderer";
import { QaSolar } from "./qa/QaSolar";
import { QA_RENDERER_PATH } from "./qa/qaPage";
import { QA_REFERENCE_PATH } from "./qa/referencePage";
import { QA_SOLAR_PATH } from "./qa/solarPage";
import { Replay } from "./replay/Replay";
import "./styles.css";

const root = document.getElementById("root");
if (root === null) {
  throw new Error("index.html has no #root element");
}

// The renderer's canonical screenshot page, the builder, and the landing page at the
// bare address; every other address is the viewer.
const path = location.pathname.replace(/\/$/, "");
const page =
  path === QA_RENDERER_PATH ? (
    <QaRenderer search={location.search} />
  ) : path === QA_GREENHOUSE_PATH ? (
    <QaGreenhouse search={location.search} />
  ) : path === QA_LAYOUT_PATH ? (
    <QaLayout search={location.search} />
  ) : path === QA_PLANTS_PATH ? (
    <QaPlants />
  ) : path === QA_AIRFLOW_PATH ? (
    <QaAirflow search={location.search} />
  ) : path === QA_SOLAR_PATH ? (
    <QaSolar search={location.search} />
  ) : path === QA_REFERENCE_PATH ? (
    <QaReference search={location.search} />
  ) : path === QA_DESIGN_PATH ? (
    <QaDesign />
  ) : path === BUILDER_PATH ? (
    <Builder />
  ) : pageAt(location.pathname, location.search) === "landing" ? (
    <Landing />
  ) : pageAt(location.pathname, location.search) === "replay" ? (
    <Replay />
  ) : (
    <App />
  );

// The golden views compare the scene drawn: their captions keep the light
// panels they were drawn with (#208); the viewer and the builder show the
// theme chosen, and the design system's page the one its address says. Set before
// the first render, so that the panels never show the other first.
showTheme(
  page.type === QaDesign
    ? designTheme(location.search)
    : page.type === App || page.type === Builder || page.type === Landing || page.type === Replay
      ? storedTheme()
      : "light",
);

createRoot(root).render(<StrictMode>{page}</StrictMode>);
