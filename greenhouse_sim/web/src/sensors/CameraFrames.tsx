import { MathUtils } from "three";

import { describeTime } from "../fields/ClimateTime";
import { formatPoint, formatValue } from "../readouts";
import {
  type CameraFrame,
  type CameraPose,
  framesOf,
  lookingAlong,
  type SensorReadingsState,
  secondsInto,
} from "./readings";

// Angles to a tenth of a degree.
const ANGLE_DECIMALS = 1;
// What a frame holds, in words.
const MODALITY_NAMES: Readonly<Record<string, string>> = { RGB: "RGB", DEPTH: "depth" };

/** Which way a camera looks, in words: turned from along the house, left
 * or right, and tilted up or down. */
export function describeLooking(pose: CameraPose): string {
  const { x, y, z } = lookingAlong(pose);
  const turn = MathUtils.radToDeg(Math.atan2(y, x));
  const tilt = MathUtils.radToDeg(Math.atan2(z, Math.hypot(x, y)));
  const across =
    formatAngle(turn) === formatAngle(0)
      ? "along the house"
      : `${formatAngle(turn)}° ${turn < 0 ? "right" : "left"} of along the house`;
  const upwards =
    formatAngle(tilt) === formatAngle(0)
      ? "level"
      : `${formatAngle(tilt)}° ${tilt < 0 ? "down" : "up"}`;
  return `${across}, ${upwards}`;
}

function formatAngle(degrees: number): string {
  return Math.abs(degrees).toFixed(ANGLE_DECIMALS);
}

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
        <dd data-testid="camera-frame-from">
          {formatPoint({ x: latest.pose.x_m, y: latest.pose.y_m, z: latest.pose.z_m })}
        </dd>
        <dt>Looking</dt>
        <dd data-testid="camera-frame-looking">{describeLooking(latest.pose)}</dd>
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
