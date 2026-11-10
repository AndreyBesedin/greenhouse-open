import { dayCount } from "../clock";
import { Button } from "../design/Button";
import { useLoad } from "../useLoad";
import {
  describeEnvironment,
  loadLabEnvironments,
  PLANT_LAB_ENVIRONMENTS_URL,
} from "./environments";
import { type LabRun, PLANT_LAB_LAST_DAY } from "./lab";

// The choice of no second environment beside the first.
const NOTHING_BESIDE = "";
// How fast the lab can play its run, in days a second at most: each day is
// shown once the simulator has grown it, so a slow answer slows the play.
const SLOW_DAYS_A_SECOND = 1;
const MEDIUM_DAYS_A_SECOND = 2;
const FAST_DAYS_A_SECOND = 5;
export const GROWTH_SPEEDS = [
  SLOW_DAYS_A_SECOND,
  MEDIUM_DAYS_A_SECOND,
  FAST_DAYS_A_SECOND,
] as const;
export type GrowthSpeed = (typeof GROWTH_SPEEDS)[number];

/**
 * The plant lab's run: its day, its seed and its plants' environments.
 * Moving the slider asks the simulator for its row on that day, so its
 * development stays the simulator's; the day shown is the day of the scene on
 * show, which the slider leads while the next arrives. Another seed draws
 * another row of the same crop. With a second environment beside the first,
 * every second plant lives in it instead, so the two can be compared side by
 * side.
 */
export function LabControls({
  run,
  shownDay,
  onChange,
  playing,
  speed,
  showNames,
  onPlaying,
  onSpeed,
  onShowNames,
}: {
  run: LabRun;
  /** The day of the scene on show, if one is. */
  shownDay: number | null;
  onChange: (change: Partial<LabRun>) => void;
  /** Whether the run plays, a day after another, and how fast. */
  playing: boolean;
  speed: GrowthSpeed;
  /** Whether each plant's name floats above it. */
  showNames: boolean;
  onPlaying: (playing: boolean) => void;
  onSpeed: (speed: GrowthSpeed) => void;
  onShowNames: (showNames: boolean) => void;
}) {
  const environments = useLoad(PLANT_LAB_ENVIRONMENTS_URL, (_url, fetchFn) =>
    loadLabEnvironments(fetchFn),
  );

  const known = environments.status === "loaded" ? environments.environments : {};
  const names = Object.keys(known);
  const described = (name: string | null) => {
    const environment = name === null ? undefined : known[name];
    return environment === undefined ? "" : describeEnvironment(environment);
  };

  return (
    <fieldset className="lab-controls" aria-label="Plant lab">
      <label className="lab-control">
        <span>Day</span>
        <input
          type="range"
          min={0}
          max={PLANT_LAB_LAST_DAY}
          step={1}
          value={run.day}
          aria-valuetext={`${dayCount(run.day)} in`}
          onChange={(event) => onChange({ day: Number(event.target.value) })}
        />
        {/* The days since its transplant, a count: "30 days in". */}
        <span data-testid="plant-day">{shownDay === null ? "…" : `${dayCount(shownDay)} in`}</span>
      </label>
      <div className="lab-control">
        <Button
          size="compact"
          onClick={() => onPlaying(!playing)}
          disabled={!playing && run.day >= PLANT_LAB_LAST_DAY}
        >
          {playing ? "Pause the run" : "Play the run"}
        </Button>
        <label>
          Growth speed{" "}
          <select
            value={speed}
            onChange={(event) => onSpeed(Number(event.target.value) as GrowthSpeed)}
          >
            {GROWTH_SPEEDS.map((daysPerSecond) => (
              <option key={daysPerSecond} value={daysPerSecond}>
                {daysPerSecond} {daysPerSecond === 1 ? "day" : "days"} a second
              </option>
            ))}
          </select>
        </label>
        <label>
          <input
            type="checkbox"
            checked={showNames}
            onChange={(event) => onShowNames(event.target.checked)}
          />{" "}
          Plant names
        </label>
      </div>
      <label className="lab-control">
        <span>Seed</span>
        <input
          type="number"
          min={0}
          step={1}
          value={run.seed}
          onChange={(event) => {
            const next = Number(event.target.value);
            if (Number.isInteger(next) && next >= 0) {
              onChange({ seed: next });
            }
          }}
        />
        <Button size="compact" onClick={() => onChange({ seed: run.seed + 1 })}>
          Another seed
        </Button>
      </label>
      {environments.status === "unavailable" && (
        <p role="alert">The lab's environments are not available: {environments.reason}.</p>
      )}
      {names.length > 0 && (
        <>
          <label className="lab-control">
            <span>Environment</span>
            <select
              value={run.environment}
              onChange={(event) => onChange({ environment: event.target.value })}
            >
              {names.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            <span data-testid="lab-environment">{described(run.environment)}</span>
          </label>
          <label className="lab-control">
            <span>Beside it</span>
            <select
              value={run.versus ?? NOTHING_BESIDE}
              onChange={(event) =>
                onChange({
                  versus: event.target.value === NOTHING_BESIDE ? null : event.target.value,
                })
              }
            >
              <option value={NOTHING_BESIDE}>nothing else</option>
              {names.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
            <span data-testid="lab-versus">{described(run.versus)}</span>
          </label>
        </>
      )}
    </fieldset>
  );
}
