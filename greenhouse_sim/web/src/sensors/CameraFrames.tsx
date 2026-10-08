import { describeTime } from "../fields/ClimateTime";
import { formatPoint, formatValue } from "../readouts";
import { type CameraFrame, framesOf, type SensorReadingsState, secondsInto } from "./readings";

// What a frame holds, in words.
const MODALITY_NAMES: Readonly<Record<string, string>> = { RGB: "RGB", DEPTH: "depth" };

function describeModalities(frame: CameraFrame): string {
  return frame.modalities.map((modality) => MODALITY_NAMES[modality] ?? modality).join(" and ");
}

/**
 * A selected camera's frames up to the moment drawn, as the run's log
 * records them: how many, the latest one's metadata (when it was taken, from
 * where, looking where, and with what intrinsics), and when each was taken.
 */
export function CameraFrames({
  cameraId,
  state,
}: {
  cameraId: string;
  state: SensorReadingsState;
}) {
  if (state.status === "none") {
    return null;
  }
  if (state.status !== "loaded") {
    return (
      <section className="camera-frames" aria-label="Frames">
        <p data-testid="camera-frames">
          {state.status === "loading"
            ? "Reading the camera's frames…"
            : `The camera's frames cannot be read: ${state.reason}.`}
        </p>
      </section>
    );
  }
  const { readings } = state;
  const frames = framesOf(readings, cameraId);
  const latest = frames.at(-1);
  if (latest === undefined) {
    return (
      <section className="camera-frames" aria-label="Frames">
        <p data-testid="camera-frames">No frames yet.</p>
      </section>
    );
  }
  const at = (frame: CameraFrame) => describeTime(secondsInto(readings.start, frame.timestamp));
  const { width, height, fx, fy } = latest.intrinsics;
  return (
    <section className="camera-frames" aria-label="Frames">
      <p data-testid="camera-frames">
        {frames.length} {frames.length === 1 ? "frame" : "frames"} by {at(latest)}, each{" "}
        {describeModalities(latest)}.
      </p>
      <dl>
        <dt>Latest frame</dt>
        <dd data-testid="camera-frame-id">{latest.frame_id}</dd>
        <dt>Taken at</dt>
        <dd data-testid="camera-frame-time">{at(latest)}</dd>
        <dt>From (m)</dt>
        <dd data-testid="camera-frame-from">{formatPoint(latest.position)}</dd>
        <dt>Towards (m)</dt>
        <dd data-testid="camera-frame-towards">{formatPoint(latest.target)}</dd>
        <dt>Picture</dt>
        <dd data-testid="camera-frame-picture">
          {width} × {height} px, fx {formatValue(fx)} px, fy {formatValue(fy)} px
        </dd>
      </dl>
      <ol className="camera-frame-history" aria-label="Frames taken">
        {[...frames].reverse().map((frame) => (
          <li key={frame.frame_id}>{at(frame)}</li>
        ))}
      </ol>
    </section>
  );
}
