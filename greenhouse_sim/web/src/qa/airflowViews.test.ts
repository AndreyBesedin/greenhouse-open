import { describe, expect, it } from "vitest";

import {
  QA_AIRFLOW_POSES,
  QA_AIRFLOW_SLICE,
  QA_AIRFLOW_VIEWS,
  qaAirflowView,
} from "./airflowViews";

describe("the airflow QA page's views", () => {
  it("are chosen by the address, the vectors by default", () => {
    expect(qaAirflowView("")).toBe("vectors");
    expect(qaAirflowView("?view=slice")).toBe("slice");
    expect(qaAirflowView("?view=wake")).toBeNull();
  });

  it("look at the house's middle, the slice from above through the block", () => {
    for (const view of QA_AIRFLOW_VIEWS) {
      const { position, target } = QA_AIRFLOW_POSES[view];
      expect(target.x).toBe(6);
      expect(position.z).toBeGreaterThan(target.z);
    }
    const top = QA_AIRFLOW_POSES.slice;
    expect(Math.hypot(top.position.x - top.target.x, top.position.y - top.target.y)).toBeLessThan(
      0.01,
    );
    // Halfway up the 1.5 m block.
    expect(QA_AIRFLOW_SLICE).toEqual({ quantity: "speed", axis: "z", position: 0.75 });
  });
});
