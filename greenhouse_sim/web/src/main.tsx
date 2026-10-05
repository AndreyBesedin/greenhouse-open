import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";
import { QaRenderer } from "./qa/QaRenderer";
import { QA_RENDERER_PATH } from "./qa/qaPage";
import "./styles.css";

const root = document.getElementById("root");
if (root === null) {
  throw new Error("index.html has no #root element");
}

// The renderer's canonical screenshot page; every other address is the viewer.
const page =
  location.pathname.replace(/\/$/, "") === QA_RENDERER_PATH ? (
    <QaRenderer search={location.search} />
  ) : (
    <App />
  );

createRoot(root).render(<StrictMode>{page}</StrictMode>);
