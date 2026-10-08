import { Fragment, type ReactNode } from "react";
import { Quaternion, Vector3 } from "three";

import { semanticType } from "./debug/categories";
import type { OverlayToggles } from "./debug/overlays";
import { formatPoint, formatRotation, formatSize, formatValue } from "./readouts";
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
      return `plane, ${formatSize(shape.size_x)} × ${formatSize(shape.size_y)} m`;
    case "cylinder":
      return `cylinder, radius ${formatSize(shape.radius)} m, height ${formatSize(shape.height)} m`;
    case "box":
      return `box, ${formatSize(shape.size_x)} × ${formatSize(shape.size_y)} × ${formatSize(shape.size_z)} m`;
    case "polygon":
      return `polygon, ${shape.points.length} corners`;
    case "sphere":
      return `sphere, radius ${formatSize(shape.radius)} m`;
    case "ellipsoid":
      return `ellipsoid, ${formatSize(shape.size_x)} × ${formatSize(shape.size_y)} × ${formatSize(shape.size_z)} m`;
    case "axes":
      return `axes, ${formatSize(shape.length)} m`;
  }
}

/** An entity's size in words: a box's length (along its own x), width and
 * height; a cylinder's diameter and its height, standing, or length, lying. */
export function describeDimensions(entity: SceneEntity): string | null {
  const { shape } = entity;
  switch (shape.shape) {
    case "box":
      return `length ${formatSize(shape.size_x)} m, width ${formatSize(shape.size_y)} m, height ${formatSize(shape.size_z)} m`;
    case "cylinder": {
      const { w, x, y, z } = entity.transform.rotation;
      const axis = new Vector3(0, 0, 1).applyQuaternion(new Quaternion(x, y, z, w));
      const extent = Math.abs(axis.z) > UPRIGHT_COSINE ? "height" : "length";
      return `diameter ${formatSize(2 * shape.radius)} m, ${extent} ${formatSize(shape.height)} m`;
    }
    case "plane":
      return `${formatSize(shape.size_x)} × ${formatSize(shape.size_y)} m`;
    case "sphere":
      return `diameter ${formatSize(2 * shape.radius)} m`;
    case "ellipsoid":
      return `length ${formatSize(shape.size_x)} m, width ${formatSize(shape.size_y)} m, thickness ${formatSize(shape.size_z)} m`;
    case "polygon":
    case "axes":
      return null;
  }
}

/** The selected entity's identity, what it is, its transform, shape, size and
 * properties, and the overlays drawn around it; led by what it senses, for a
 * sensor or a camera. */
export function Inspector({
  entity,
  overlays,
  onOverlays,
  onClear,
  children,
}: {
  entity: SceneEntity;
  overlays: OverlayToggles;
  onOverlays: (overlays: OverlayToggles) => void;
  onClear: () => void;
  children?: ReactNode;
}) {
  const dimensions = describeDimensions(entity);
  return (
    <section className="inspector" aria-label="Inspector">
      {children}
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
