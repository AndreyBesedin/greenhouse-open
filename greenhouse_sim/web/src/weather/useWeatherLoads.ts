import type { ScenarioRun } from "../scene/run";
import { useLoad } from "../useLoad";
import { loadWeather, loadWeatherDay, weatherDayUrl, weatherUrl } from "./weather";

/** The weather outside a scenario's run at the moment drawn, and through its
 * day, for its chart; nothing without a scenario's run. */
export function useWeatherLoads(run: ScenarioRun | null) {
  const moment = run?.time ?? 0;
  const weather = useLoad(
    run === null ? null : weatherUrl(run.scenarioId, moment, run.weather),
    loadWeather,
  );
  const weatherDay = useLoad(
    run === null ? null : weatherDayUrl(run.scenarioId, moment, run.weather),
    loadWeatherDay,
  );
  return { weather, weatherDay };
}
