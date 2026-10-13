import { useEffect, useState } from "react";

// The `Server-Timing` metric the simulator's API says its time in (P09.8).
const SIMULATOR_METRIC = "sim";
const API_PREFIX = "/api/";

/** How long the simulator took to answer a request, and which: its path
 * under `/api/`, without its query. */
export interface SimulatorTime {
  path: string;
  ms: number;
}

/** The simulator's time for a request the page made, from the browser's
 * timing of it; null for a request that is not the API's, or that does not
 * say. */
export function simulatorTimeOf(
  entry: Pick<PerformanceResourceTiming, "name" | "serverTiming">,
  origin: string = location.origin,
): SimulatorTime | null {
  const url = new URL(entry.name, origin);
  if (url.origin !== origin || !url.pathname.startsWith(API_PREFIX)) {
    return null;
  }
  const said = entry.serverTiming?.find((timing) => timing.name === SIMULATOR_METRIC);
  return said === undefined
    ? null
    : { path: url.pathname.slice(API_PREFIX.length), ms: said.duration };
}

/** The simulator's time for the latest request to the API that has
 * answered, as the browser times every request the page makes; null until
 * one has. */
export function useSimulatorTime(): SimulatorTime | null {
  const [latest, setLatest] = useState<SimulatorTime | null>(null);
  useEffect(() => {
    if (typeof PerformanceObserver === "undefined") {
      return;
    }
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const time = simulatorTimeOf(entry as PerformanceResourceTiming);
        if (time !== null) {
          setLatest(time);
        }
      }
    });
    observer.observe({ type: "resource", buffered: true });
    return () => observer.disconnect();
  }, []);
  return latest;
}

/** The simulator's time in words: "1,234 ms for scenarios/climate_box/fields". */
export function describeSimulatorTime(time: SimulatorTime): string {
  return `${Math.round(time.ms).toLocaleString("en-US")} ms for ${time.path}`;
}
