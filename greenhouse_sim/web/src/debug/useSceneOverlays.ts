import { useMemo } from "react";

import type { SliceQuantity } from "../fields/display";
import type { EnvironmentField } from "../fields/field";
import { type OpeningsAt, openingFlowOverlays } from "../fields/openingFlows";
import { probeOverlays } from "../fields/probes";
import { describePlantLight, type PlantsLight } from "../plants/light";
import { plantNameOverlays } from "../plants/names";
import { worldAxesLength } from "../SeenInTheView";
import type { SceneEntity, SceneSnapshot } from "../scene/generated/snapshotTypes";
import { frustumOverlays } from "../sensors/camera";
import { sceneSunlight, sunPathOverlays } from "../weather/sunlight";
import {
  sunOverlays,
  type WeatherAtAMoment,
  type WeatherDay,
  windOverlays,
} from "../weather/weather";
import type { Point3 } from "../world";
import { sceneDimensionOverlays } from "./dimensions";
import {
  type OverlayToggles,
  type ScenePrimitives,
  selectionOverlays,
  shownPrimitives,
} from "./overlays";

/**
 * What is drawn over a scene, worked out from it, which they only read:
 *
 * - the sun's light in a climate run's view (`sunlit`), and the sun at the
 *   moment (`outside`), above the horizon only, and its day's path
 *   (`sunsDay`), each loading on its own, so that "What am I seeing?" says
 *   which is drawn; every other view keeps the fixed light;
 * - each overlay over the scene, shown or hidden (`scenePrimitives`): what
 *   the open doors and vents pass (`flowing`), the wind, the sun, the
 *   cameras' views and the probes, coloured by the slice's quantity in QA
 *   mode; hiding one leaves out its primitives, never what they are drawn
 *   from;
 * - the selected item's outline (`drawnSelected`, where it is drawn), the
 *   scene's dimensions if asked for, and every plant's name if asked for
 *   (`showingNames`), with its day's light (`lightOn`) where it is read;
 * - the kinds the scene holds, and how long its world axes are, for what
 *   the card says the scene draws.
 */
export function useSceneOverlays({
  snapshot,
  sunlit,
  outside,
  sunsDay,
  flowing,
  probes,
  probedField,
  probeQuantity,
  drawnSelected,
  toggles,
  showDimensions,
  showingNames,
  lightOn,
}: {
  snapshot: SceneSnapshot | null;
  sunlit: boolean;
  outside: WeatherAtAMoment | null;
  sunsDay: WeatherDay | null;
  flowing: OpeningsAt | null;
  probes: readonly Point3[];
  probedField: EnvironmentField | null;
  probeQuantity: SliceQuantity | null;
  drawnSelected: SceneEntity | null;
  toggles: OverlayToggles;
  showDimensions: boolean;
  showingNames: boolean;
  lightOn: PlantsLight | null;
}) {
  const sunlight = useMemo(
    () =>
      !sunlit || snapshot === null || outside === null ? null : sceneSunlight(snapshot, outside),
    [sunlit, snapshot, outside],
  );
  const sunNow = useMemo(
    () => (snapshot === null || outside === null ? [] : sunOverlays(snapshot, outside)),
    [snapshot, outside],
  );
  const sunPath = useMemo(
    () => (snapshot === null || sunsDay === null ? [] : sunPathOverlays(snapshot, sunsDay)),
    [snapshot, sunsDay],
  );
  const scenePrimitives: ScenePrimitives = useMemo(
    () => ({
      openingFlows:
        snapshot === null || flowing === null ? [] : openingFlowOverlays(snapshot, flowing),
      wind: snapshot === null || outside === null ? [] : windOverlays(snapshot, outside),
      sun: [...sunNow, ...sunPath],
      cameraViews: snapshot === null ? [] : frustumOverlays(snapshot),
      probes: probedField === null ? [] : probeOverlays(probes, probedField, probeQuantity),
    }),
    [snapshot, flowing, outside, sunNow, sunPath, probes, probedField, probeQuantity],
  );
  const overlays = useMemo(
    () => [
      ...(drawnSelected === null ? [] : selectionOverlays(drawnSelected, toggles)),
      ...(snapshot !== null && showDimensions ? sceneDimensionOverlays(snapshot) : []),
      ...(snapshot !== null && showingNames
        ? plantNameOverlays(snapshot, (plantId) =>
            lightOn === null ? null : (describePlantLight(lightOn, plantId)?.day ?? null),
          )
        : []),
      ...shownPrimitives(scenePrimitives, toggles),
    ],
    [drawnSelected, toggles, snapshot, showDimensions, showingNames, lightOn, scenePrimitives],
  );
  const kindsShown = useMemo(
    () => (snapshot === null ? null : new Set(snapshot.entities.map((entity) => entity.kind))),
    [snapshot],
  );
  const axesLengthM = useMemo(() => worldAxesLength(snapshot), [snapshot]);
  return { sunlight, sunNow, sunPath, scenePrimitives, overlays, kindsShown, axesLengthM };
}
