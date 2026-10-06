import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { QA_GREENHOUSE_PATH } from "./qa/greenhouseViews";
import { QaGreenhouse } from "./qa/QaGreenhouse";
import { QaRenderer } from "./qa/QaRenderer";
import { QA_RENDERER_PATH } from "./qa/qaPage";
import "./styles.css";

const root = document.getElementById("root");
if (root === null) {
  throw new Error("index.html has no #root element");
}

// The renderer's canonical screenshot page; every other address is the viewer.
const path = location.pathname.replace(/\/$/, "");
const page =
  path === QA_RENDERER_PATH ? (
    <QaRenderer search={location.search} />
  ) : path === QA_GREENHOUSE_PATH ? (
    <QaGreenhouse search={location.search} />
  ) : (
    <App />
  );

createRoot(root).render(<StrictMode>{page}</StrictMode>);
