import { formatSpeed } from "./readouts";
import { LIVE_SPEEDS, type LiveCommand, type LiveFrame } from "./scene/live";

// The simulator's own pace, shown until the first frame says otherwise.
const NORMAL_SPEED = 1;

/**
 * Play, pause, step, reset and speed for the live run being followed. The
 * controls show the run's state as the latest frame reports it, so they
 * change only once the simulator has taken a command.
 */
export function TimeControls({
  frame,
  connected,
  onCommand,
}: {
  frame: LiveFrame | null;
  connected: boolean;
  onCommand: (command: LiveCommand) => void;
}) {
  const playing = frame?.playing ?? true;
  return (
    <fieldset className="time-controls" aria-label="Time controls" disabled={!connected || !frame}>
      <button type="button" onClick={() => onCommand(playing ? "pause" : "play")}>
        {playing ? "Pause" : "Play"}
      </button>
      <button type="button" disabled={playing} onClick={() => onCommand("step")}>
        Step
      </button>
      <button type="button" onClick={() => onCommand("reset")}>
        Reset
      </button>
      <label>
        Speed{" "}
        <select
          value={frame?.speed ?? NORMAL_SPEED}
          onChange={(event) => onCommand({ speed: Number(event.target.value) })}
        >
          {LIVE_SPEEDS.map((speed) => (
            <option key={speed} value={speed}>
              {formatSpeed(speed)}
            </option>
          ))}
        </select>
      </label>
    </fieldset>
  );
}
