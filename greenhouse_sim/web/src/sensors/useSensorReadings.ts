import { useState } from "react";

import type { SceneEntity } from "../scene/generated/snapshotTypes";
import { runsSomething, type ScenarioRun } from "../scene/run";
import { useLoad } from "../useLoad";
import { loadSensorReadings, sensorsKey } from "./readings";

/**
 * The run's observation log up to the moment drawn, while a sensor or a
 * camera is `selected`, and, in QA mode only, what its sensors truly
 * sampled; and what they read through the same run all off, when something
 * runs. Sensors' readings are shown as they err unless, in QA mode, the
 * viewer asks for clean ones' (`imperfect`).
 */
export function useSensorReadings(
  selected: SceneEntity | null,
  run: ScenarioRun | null,
  qaMode: boolean,
) {
  const [imperfect, setImperfect] = useState(true);
  const sensorSelected = selected?.kind === "SENSOR" || selected?.kind === "CAMERA";
  const sensorRun = sensorSelected ? run : null;
  const clean = qaMode && !imperfect;
  const readings = useLoad(
    sensorRun === null
      ? null
      : { scenarioId: sensorRun.scenarioId, run: { ...sensorRun, clean }, truth: qaMode },
    loadSensorReadings,
    { key: sensorsKey },
  );
  const allOff = useLoad(
    sensorRun === null || !runsSomething(sensorRun)
      ? null
      : {
          scenarioId: sensorRun.scenarioId,
          run: {
            ...sensorRun,
            levels: undefined,
            schedule: undefined,
            daily: [],
            clean,
          },
          truth: false,
        },
    loadSensorReadings,
    { key: sensorsKey },
  );
  return { readings, allOff, imperfect, setImperfect };
}
