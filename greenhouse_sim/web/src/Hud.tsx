import { PRESET_ORDER, type PresetName } from "./camera";
import { formatMetres, formatPoint, type ViewSample } from "./readouts";
import type { Point3 } from "./world";

const PRESET_LABELS: Record<PresetName, string> = {
  top: "Top",
  front: "Front",
  side: "Side",
  isometric: "Isometric",
};

const PENDING = "…";

export function Hud({
  sample,
  pointer,
  onPreset,
}: {
  sample: ViewSample | null;
  pointer: Point3 | null;
  onPreset: (preset: PresetName) => void;
}) {
  return (
    <section className="hud" aria-label="View">
      <fieldset aria-label="Camera presets">
        {PRESET_ORDER.map((preset) => (
          <button type="button" key={preset} onClick={() => onPreset(preset)}>
            {PRESET_LABELS[preset]}
          </button>
        ))}
      </fieldset>
      <dl>
        <dt>Camera (m)</dt>
        <dd data-testid="camera-position">{sample ? formatPoint(sample.camera) : PENDING}</dd>
        <dt>Pointer on ground (m)</dt>
        <dd data-testid="pointer-position">
          {pointer ? `x ${formatMetres(pointer.x)}, y ${formatMetres(pointer.y)}` : "—"}
        </dd>
        <dt>Frame rate</dt>
        <dd data-testid="frame-rate">
          {sample ? `${Math.round(sample.framesPerSecond)} fps` : PENDING}
        </dd>
        <dt>Objects</dt>
        <dd data-testid="object-count">{sample ? sample.objects : PENDING}</dd>
      </dl>
    </section>
  );
}
