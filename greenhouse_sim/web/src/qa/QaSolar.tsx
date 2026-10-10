import { useEffect, useMemo, useState } from "react";

import { quantityScale } from "../fields/drawing";
import { FieldLegend } from "../fields/FieldLegend";
import { FieldSlice } from "../fields/FieldSlice";
import { Viewport } from "../Viewport";
import { sceneSunlight, sunPathOverlays } from "../weather/sunlight";
import { describeSun, sunOverlays } from "../weather/weather";
import {
  parseSolarLight,
  QA_SOLAR_LIGHT_URL,
  QA_SOLAR_POSE,
  QA_SOLAR_SCENE_URL,
  QA_SOLAR_SLICE,
  qaSolarView,
  type SolarLight,
  solarRange,
} from "./solarViews";
import { useSceneFile } from "./useSceneFile";

const ignore = () => undefined;

type LightState =
  | { status: "loading" }
  | { status: "missing"; reason: string }
  | { status: "loaded"; light: SolarLight };

/**
 * The canonical page for P08's screenshot tests: the solar lab on its clear
 * equinox day, in the morning, at noon or in the evening, lit from the sun
 * where it stands then, with its path across the sky, and the PAR on the
 * floor's cells' level as a slice, on one scale for all three. Nothing on it
 * changes over time, so it looks the same on every visit.
 */
export function QaSolar({ search }: { search: string }) {
  const view = qaSolarView(search);
  const scene = useSceneFile(QA_SOLAR_SCENE_URL);
  const [light, setLight] = useState<LightState>({ status: "loading" });
  useEffect(() => {
    let current = true;
    void fetch(QA_SOLAR_LIGHT_URL)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`the file answered ${response.status}`);
        }
        return parseSolarLight(await response.json());
      })
      .then(
        (parsed) => current && setLight({ status: "loaded", light: parsed }),
        (error: unknown) =>
          current &&
          setLight({
            status: "missing",
            reason: error instanceof Error ? error.message : String(error),
          }),
      );
    return () => {
      current = false;
    };
  }, []);

  const snapshot = scene.status === "loaded" ? scene.snapshot : null;
  const loaded = light.status === "loaded" ? light.light : null;
  const moment = view === null || loaded === null ? null : loaded.views[view];
  const overlays = useMemo(
    () =>
      snapshot === null || loaded === null || moment === null
        ? []
        : [...sunOverlays(snapshot, moment.weather), ...sunPathOverlays(snapshot, loaded.day)],
    [snapshot, loaded, moment],
  );
  const sunlight = useMemo(
    () => (snapshot === null || moment === null ? null : sceneSunlight(snapshot, moment.weather)),
    [snapshot, moment],
  );

  if (view === null) {
    return (
      <p className="qa-caption" role="alert">
        The view must be morning, noon or evening.
      </p>
    );
  }
  if (snapshot === null || loaded === null || moment === null) {
    const loading = scene.status === "loading" || light.status === "loading";
    return (
      <p className="qa-caption" data-testid="qa-caption">
        {loading ? "Loading the solar QA case…" : "The solar QA case is missing."}
      </p>
    );
  }
  const range = solarRange(loaded);
  const scale = quantityScale(moment.field, QA_SOLAR_SLICE.quantity);
  return (
    <main className="viewer">
      <Viewport
        snapshot={snapshot}
        presetRequest={null}
        initialPose={QA_SOLAR_POSE}
        overlays={overlays}
        sunlight={sunlight}
        onSample={ignore}
        onPointer={ignore}
        onSelect={ignore}
      >
        <FieldSlice field={moment.field} slice={QA_SOLAR_SLICE} range={range} />
      </Viewport>
      <p className="qa-caption" data-testid="qa-caption">
        Solar QA, {view} view: sun {describeSun(moment.weather.sun)}
      </p>
      {scale !== null && (
        <div className="legends">
          <FieldLegend
            title={scale.title}
            unit={scale.unit}
            range={range}
            own={range}
            onRange={ignore}
          />
        </div>
      )}
    </main>
  );
}
