import { useEffect, useState } from "react";

import { quantityScale } from "../fields/drawing";
import { FieldArrows } from "../fields/FieldArrows";
import { FieldLegend } from "../fields/FieldLegend";
import { FieldSlice } from "../fields/FieldSlice";
import { type FieldState, fetchField } from "../fields/source";
import { Viewport } from "../Viewport";
import {
  QA_AIRFLOW_FIELD_URL,
  QA_AIRFLOW_POSES,
  QA_AIRFLOW_SCENE_URL,
  QA_AIRFLOW_SLICE,
  qaAirflowView,
} from "./airflowViews";
import { useSceneFile } from "./useSceneFile";

const ignore = () => undefined;

/**
 * The canonical page for the airflow's screenshot tests: the airflow QA
 * scenario, air blown past a block from door to door, with its air as
 * OpenFOAM solved it drawn as arrows at every cell, or as a slice of its
 * speed through the block. Nothing on it changes over time, so it looks the
 * same on every visit.
 */
export function QaAirflow({ search }: { search: string }) {
  const view = qaAirflowView(search);
  const scene = useSceneFile(QA_AIRFLOW_SCENE_URL);
  const [field, setField] = useState<FieldState>({ status: "loading" });
  useEffect(() => {
    let current = true;
    void fetchField(QA_AIRFLOW_FIELD_URL).then((state) => {
      if (current) {
        setField(state);
      }
    });
    return () => {
      current = false;
    };
  }, []);

  if (view === null) {
    return (
      <p className="qa-caption" role="alert">
        The view must be vectors or slice.
      </p>
    );
  }
  if (scene.status !== "loaded" || field.status !== "loaded") {
    const loading = scene.status === "loading" || field.status === "loading";
    return (
      <p className="qa-caption" data-testid="qa-caption">
        {loading ? "Loading the airflow QA case…" : "The airflow QA case is missing."}
      </p>
    );
  }
  const slice = view === "slice" ? QA_AIRFLOW_SLICE : null;
  const scale = quantityScale(field.field, slice === null ? "speed" : slice.quantity);
  return (
    <main className="viewer">
      <Viewport
        snapshot={scene.snapshot}
        presetRequest={null}
        initialPose={QA_AIRFLOW_POSES[view]}
        onSample={ignore}
        onPointer={ignore}
        onSelect={ignore}
      >
        {scale !== null &&
          (slice === null ? (
            <FieldArrows field={field.field} range={scale.range} />
          ) : (
            <FieldSlice field={field.field} slice={slice} range={scale.range} />
          ))}
      </Viewport>
      <p className="qa-caption" data-testid="qa-caption">
        Airflow QA, {view} view
      </p>
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
