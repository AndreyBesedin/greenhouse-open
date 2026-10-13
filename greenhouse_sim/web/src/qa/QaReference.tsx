import { useMemo } from "react";

import { describeTime } from "../fields/ClimateTime";
import { FieldArrows } from "../fields/FieldArrows";
import { FieldLegend } from "../fields/FieldLegend";
import { FieldSlice } from "../fields/FieldSlice";
import { openingFlowOverlays, withOpeningFlows } from "../fields/openingFlows";
import { withCrop } from "../plants/crop";
import { CameraView } from "../sensors/CameraView";
import { cameraOf } from "../sensors/camera";
import { useLoad } from "../useLoad";
import { Viewport } from "../Viewport";
import { sceneSunlight, sunPathOverlays } from "../weather/sunlight";
import { sunOverlays } from "../weather/weather";
import {
  describeProbes,
  loadReferenceQa,
  QA_REFERENCE_URL,
  qaReferenceView,
  REFERENCE_VIEWS,
  referenceScale,
} from "./referenceViews";

const ignore = () => undefined;
// The path camera's picture across the page, in CSS pixels: its own 640.
const CAMERA_WIDTH_PX = 640;

/**
 * The canonical page for P09's golden views of the reference greenhouse:
 * its run at a moment of its opening day, or of a young crop's, drawn from
 * a fixed view, lit by the sun where it stands then. Each view shows one
 * thing: the sun at dawn, noon or evening, with its path; the air as arrows,
 * the fans on or off; a slice of its temperature across the house, the
 * vents open or shut; a young crop and a fruiting one; the path camera's
 * picture and its depth; a slice of the air's speed along a fan's jet, and
 * of the light in the canopy. Its state probes are said under it. Nothing
 * on it changes over time, so it looks the same on every visit.
 */
export function QaReference({ search }: { search: string }) {
  const view = qaReferenceView(search);
  const state = useLoad(QA_REFERENCE_URL, loadReferenceQa);
  const qa = state.status === "loaded" ? state.qa : null;
  const drawn = view === null ? null : REFERENCE_VIEWS[view];
  const moment = qa === null || drawn === null ? null : qa.moments[drawn.moment];

  const snapshot = useMemo(() => {
    if (qa === null || moment === null) {
      return null;
    }
    const crop = qa.crops[String(moment.cropDay)];
    const cropped = crop === undefined ? moment.house : withCrop(moment.house, crop);
    return moment.openings === null ? cropped : withOpeningFlows(cropped, moment.openings);
  }, [qa, moment]);
  const overlays = useMemo(() => {
    if (qa === null || moment === null || drawn === null || snapshot === null) {
      return [];
    }
    return [
      ...(drawn.layer.kind === "sun"
        ? [...sunOverlays(snapshot, moment.weather), ...sunPathOverlays(snapshot, qa.sunPath)]
        : []),
      ...(moment.openings === null ? [] : openingFlowOverlays(snapshot, moment.openings)),
    ];
  }, [qa, moment, drawn, snapshot]);
  const sunlight = useMemo(
    () => (snapshot === null || moment === null ? null : sceneSunlight(snapshot, moment.weather)),
    [snapshot, moment],
  );

  if (view === null || drawn === null) {
    return (
      <p className="qa-caption" role="alert">
        There is no such view of the reference greenhouse.
      </p>
    );
  }
  if (qa === null || moment === null || snapshot === null) {
    return (
      <p className="qa-caption" data-testid="qa-caption">
        {state.status === "loading"
          ? "Loading the reference greenhouse's QA…"
          : `The reference greenhouse's QA is missing${state.status === "missing" ? `: ${state.reason}` : ""}.`}
      </p>
    );
  }
  const caption = (
    <>
      <p className="qa-caption" data-testid="qa-caption">
        Reference greenhouse, {view} view: {describeTime(moment.timeS)}
      </p>
      <p className="qa-caption qa-probes" data-testid="qa-probes">
        {describeProbes(moment.probes)}
      </p>
    </>
  );
  const { layer } = drawn;
  if (layer.kind === "camera") {
    const camera = snapshot.entities.find((entity) => entity.kind === "CAMERA");
    const spec = camera === undefined ? null : cameraOf(camera);
    return (
      <main className="qa-camera">
        {spec === null ? (
          <p role="alert">The reference greenhouse has no camera.</p>
        ) : (
          <CameraView
            snapshot={snapshot}
            spec={spec}
            firstPass={layer.pass}
            widthPx={CAMERA_WIDTH_PX}
          />
        )}
        {caption}
      </main>
    );
  }
  const scale = referenceScale(qa, drawn);
  const field = moment.field;
  return (
    <main className="viewer">
      <Viewport
        snapshot={snapshot}
        presetRequest={null}
        initialPose={drawn.pose}
        overlays={overlays}
        sunlight={sunlight}
        frameloop="demand"
        onSample={ignore}
        onPointer={ignore}
        onSelect={ignore}
      >
        {field !== null &&
          scale !== null &&
          (layer.kind === "arrows" ? (
            <FieldArrows field={field} range={scale.range} />
          ) : layer.kind === "slice" ? (
            <FieldSlice field={field} slice={layer.slice} range={scale.range} />
          ) : null)}
      </Viewport>
      {caption}
      {scale !== null && (
        <div className="legends">
          <FieldLegend
            title={scale.title}
            unit={scale.unit}
            range={scale.range}
            own={scale.range}
            onRange={ignore}
          />
        </div>
      )}
    </main>
  );
}
