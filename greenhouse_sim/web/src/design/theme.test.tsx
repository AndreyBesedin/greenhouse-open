// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";

import { InfoPanel } from "../InfoPanel";
import { checkbox, click, type Rendered, render } from "../testing/render";
import { showTheme, storedTheme, useTheme } from "./theme";

const BUILD = { simulatorVersion: "0.2.0", sourceCommit: "abc1234" };

function Themed() {
  const [theme, setTheme] = useTheme();
  return (
    <InfoPanel
      build={BUILD}
      scenarios={{ status: "loading" }}
      source={{ kind: "example" }}
      scene={{ status: "none" }}
      theme={theme}
      onTheme={setTheme}
      onSource={() => undefined}
    />
  );
}

describe("the theme (#208)", () => {
  let shown: Rendered | undefined;
  afterEach(() => {
    shown?.unmount();
    localStorage.clear();
    delete document.documentElement.dataset.theme;
  });

  it("is dark unless light was chosen in this browser", () => {
    expect(storedTheme()).toBe("dark");
    localStorage.setItem("greenhouse-sim.panels", "light");
    expect(storedTheme()).toBe("light");
    localStorage.setItem("greenhouse-sim.panels", "pink");
    expect(storedTheme()).toBe("dark");
  });

  it("is switched on the info panel's last line, shown on the document and kept", () => {
    shown = render(<Themed />);
    const light = checkbox(shown.container, "Light panels");

    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(light.checked).toBe(false);
    click(light);
    expect(document.documentElement.dataset.theme).toBe("light");
    expect(localStorage.getItem("greenhouse-sim.panels")).toBe("light");
    // The build line says what it said, the switch beside it.
    expect(shown.container.querySelector('[data-testid="build-line"]')?.textContent).toBe(
      "simulator 0.2.0 · commit abc1234",
    );

    shown.unmount();
    shown = render(<Themed />);
    expect(checkbox(shown.container, "Light panels").checked).toBe(true);
  });

  it("is light on a page that only shows it so", () => {
    showTheme("light");
    expect(document.documentElement.dataset.theme).toBe("light");
  });
});
