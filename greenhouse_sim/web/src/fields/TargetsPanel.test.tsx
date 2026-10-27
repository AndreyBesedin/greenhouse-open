// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";

import { DAY_S } from "../clock";
import type { ScenarioSource } from "../scene/edits";
import { withTargetsSet } from "../scene/edits";
import type { ThermostatAt } from "../scene/equipment";
import { button, click, enter, render, said } from "../testing/render";
import { describeTargets, settingMoment, TargetsPanel } from "./TargetsPanel";

const THERMOSTAT: ThermostatAt = {
  actuatorId: "heater",
  setpointC: 18,
  dayC: 18,
  nightC: 16,
  runs: true,
};

function inputs(within: ParentNode): HTMLInputElement[] {
  return [...within.querySelectorAll<HTMLInputElement>('input[type="number"]')];
}

describe("the heating targets (#274)", () => {
  it("say in a line the setpoints in force at the moment drawn", () => {
    expect(describeTargets(THERMOSTAT)).toBe("Heating targets: 18 °C by day, 16 °C by night");
    expect(describeTargets({ ...THERMOSTAT, dayC: 24.5 })).toBe(
      "Heating targets: 24.50 °C by day, 16 °C by night",
    );
    expect(describeTargets(null)).toBe("Heating targets");
  });

  it("take effect at the moment drawn, or the next minute after it", () => {
    expect(settingMoment(0)).toBe(0);
    expect(settingMoment(3600)).toBe(3600);
    expect(settingMoment(3630)).toBe(3660);
  });

  it("start from the setpoints in force, and set only those changed", () => {
    const onSet = vi.fn();
    const view = render(
      <TargetsPanel thermostat={THERMOSTAT} time={DAY_S + 1830} followed={false} onSet={onSet} />,
    );
    const [day, night] = inputs(view.container);
    if (day === undefined || night === undefined) {
      throw new Error("no inputs");
    }

    expect([day.value, night.value]).toEqual(["18", "16"]);
    expect(said(view.container, "targets-summary")).toBe(
      "Heating targets: 18 °C by day, 16 °C by night",
    );
    // Nothing changed, nothing to set.
    const set = button(view.container, "Set from day 1, 31 min");
    expect(set.disabled).toBe(true);
    enter(day, "24");
    expect(set.disabled).toBe(false);
    click(set);
    expect(onSet).toHaveBeenCalledExactlyOnceWith({ heating_day: 24 });
    // Out of what the simulator takes, it cannot be set.
    enter(night, "55");
    expect(set.disabled).toBe(true);
    view.unmount();
  });

  it("followed, are set on the run played back from its next minute", () => {
    const onSet = vi.fn();
    const view = render(<TargetsPanel thermostat={THERMOSTAT} time={0} followed onSet={onSet} />);
    const [, night] = inputs(view.container);
    if (night === undefined) {
      throw new Error("no inputs");
    }

    enter(night, "20");
    click(button(view.container, "Set from the run's next minute"));
    expect(onSet).toHaveBeenCalledExactlyOnceWith({ heating_night: 20 });
    view.unmount();
  });

  it("not followed, are target changes in the address from the moment drawn", () => {
    const source: ScenarioSource = {
      kind: "scenario",
      scenarioId: "reference_greenhouse",
      field: "climate",
      time: 27_030,
      targets: [{ timeS: 0, target: "heating_night", valueC: 17 }],
    };

    expect(withTargetsSet(source, { heating_day: 24 }).targets).toEqual([
      { timeS: 0, target: "heating_night", valueC: 17 },
      { timeS: 27_060, target: "heating_day", valueC: 24 },
    ]);
  });
});
