import { PRESET_ORDER, type PresetName } from "./camera";
import { formatInstant, formatMetres, formatPoint, type ViewSample } from "./readouts";
import type { LiveConnection, LiveFrame } from "./scene/live";
import type { Point3 } from "./world";

const PRESET_LABELS: Record<PresetName, string> = {
  top: "Top",
  front: "Front",
  side: "Side",
  isometric: "Isometric",
};

const PENDING = "…";

const CONNECTION_LABELS: Record<LiveConnection, string> = {
  connecting: "connecting…",
  live: "live",
  disconnected: "disconnected, reconnecting…",
};

/** A live scenario's progress, when one is being followed. */
export interface LiveStatus {
  connection: LiveConnection;
  frame: LiveFrame | null;
}

export function Hud({
  sample,
  pointer,
  live = null,
  onPreset,
}: {
  sample: ViewSample | null;
  pointer: Point3 | null;
  live?: LiveStatus | null;
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
        {live && (
          <>
            <dt>Stream</dt>
            <dd data-testid="stream-status">{CONNECTION_LABELS[live.connection]}</dd>
            <dt>Simulation</dt>
            <dd data-testid="simulation-time">
              {live.frame
                ? `day ${live.frame.day} · ${formatInstant(live.frame.timestamp)}`
                : PENDING}
            </dd>
          </>
        )}
      </dl>
    </section>
  );
}
