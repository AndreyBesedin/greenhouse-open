import { Fragment } from "react";
import { Quaternion, Vector3 } from "three";

import { semanticType } from "./debug/categories";
import type { OverlayToggles } from "./debug/overlays";
import { formatMetres, formatPoint, formatRotation, formatValue } from "./readouts";
import type { SceneEntity, Shape } from "./scene/generated/snapshotTypes";

// A cylinder whose axis leans less than this from the vertical stands up.
const UPRIGHT_COSINE = 0.99;

const OVERLAY_LABELS: Record<keyof OverlayToggles, string> = {
  box: "Bounding box",
  axes: "Origin and axes",
  label: "Label",
};
const OVERLAY_ORDER: readonly (keyof OverlayToggles)[] = ["box", "axes", "label"];

export function describeShape(shape: Shape): string {
  switch (shape.shape) {
    case "plane":
      return `plane, ${formatMetres(shape.size_x)} × ${formatMetres(shape.size_y)} m`;
    case "cylinder":
      return `cylinder, radius ${formatMetres(shape.radius)} m, height ${formatMetres(shape.height)} m`;
    case "box":
      return `box, ${formatMetres(shape.size_x)} × ${formatMetres(shape.size_y)} × ${formatMetres(shape.size_z)} m`;
    case "polygon":
      return `polygon, ${shape.points.length} corners`;
    case "sphere":
      return `sphere, radius ${formatMetres(shape.radius)} m`;
    case "axes":
      return `axes, ${formatMetres(shape.length)} m`;
  }
}

/** An entity's size in words: a box's length (along its own x), width and
 * height; a cylinder's diameter and its height, standing, or length, lying. */
export function describeDimensions(entity: SceneEntity): string | null {
  const { shape } = entity;
  switch (shape.shape) {
    case "box":
      return `length ${formatMetres(shape.size_x)} m, width ${formatMetres(shape.size_y)} m, height ${formatMetres(shape.size_z)} m`;
    case "cylinder": {
      const { w, x, y, z } = entity.transform.rotation;
      const axis = new Vector3(0, 0, 1).applyQuaternion(new Quaternion(x, y, z, w));
      const extent = Math.abs(axis.z) > UPRIGHT_COSINE ? "height" : "length";
      return `diameter ${formatMetres(2 * shape.radius)} m, ${extent} ${formatMetres(shape.height)} m`;
    }
    case "plane":
      return `${formatMetres(shape.size_x)} × ${formatMetres(shape.size_y)} m`;
    case "sphere":
      return `diameter ${formatMetres(2 * shape.radius)} m`;
    case "polygon":
    case "axes":
      return null;
  }
}

/** The selected entity's identity, what it is, its transform, shape, size and
 * properties, and the overlays drawn around it. */
export function Inspector({
  entity,
  overlays,
  onOverlays,
  onClear,
}: {
  entity: SceneEntity;
  overlays: OverlayToggles;
  onOverlays: (overlays: OverlayToggles) => void;
  onClear: () => void;
}) {
  const dimensions = describeDimensions(entity);
  return (
    <section className="inspector" aria-label="Inspector">
      <dl>
        <dt>Entity</dt>
        <dd data-testid="selected-entity">{entity.entity_id}</dd>
        <dt>Kind</dt>
        <dd>{entity.kind}</dd>
        <dt>Type</dt>
        <dd data-testid="selected-type">{semanticType(entity.kind)}</dd>
        {entity.label !== null && (
          <>
            <dt>Label</dt>
            <dd>{entity.label}</dd>
          </>
        )}
        <dt>Position (m)</dt>
        <dd data-testid="selected-position">{formatPoint(entity.transform.position)}</dd>
        <dt>Rotation</dt>
        <dd data-testid="selected-rotation">{formatRotation(entity.transform.rotation)}</dd>
        <dt>Shape</dt>
        <dd data-testid="selected-shape">{describeShape(entity.shape)}</dd>
        {dimensions !== null && (
          <>
            <dt>Dimensions</dt>
            <dd data-testid="selected-dimensions">{dimensions}</dd>
          </>
        )}
        {entity.material !== null && (
          <>
            <dt>Material</dt>
            <dd data-testid="selected-material">{entity.material}</dd>
          </>
        )}
        {Object.entries(entity.properties).map(([name, value]) => (
          <Fragment key={name}>
            <dt>{name}</dt>
            <dd data-testid={`property-${name}`}>{formatValue(value)}</dd>
          </Fragment>
        ))}
      </dl>
      <fieldset aria-label="Overlays">
        {OVERLAY_ORDER.map((overlay) => (
          <label key={overlay}>
            <input
              type="checkbox"
              checked={overlays[overlay]}
              onChange={(event) => onOverlays({ ...overlays, [overlay]: event.target.checked })}
            />{" "}
            {OVERLAY_LABELS[overlay]}
          </label>
        ))}
      </fieldset>
      <button type="button" onClick={onClear}>
        Clear selection
      </button>
    </section>
  );
}
