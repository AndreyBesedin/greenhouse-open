import { Fragment } from "react";

import type { OverlayToggles } from "./debug/overlays";
import { formatMetres, formatPoint, formatRotation, formatValue } from "./readouts";
import type { SceneEntity, Shape } from "./scene/generated/snapshotTypes";

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
    case "axes":
      return `axes, ${formatMetres(shape.length)} m`;
  }
}

/** The selected entity's identity, transform, shape and properties, and the
 * overlays drawn around it. */
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
  return (
    <section className="inspector" aria-label="Inspector">
      <dl>
        <dt>Entity</dt>
        <dd data-testid="selected-entity">{entity.entity_id}</dd>
        <dt>Kind</dt>
        <dd>{entity.kind}</dd>
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
