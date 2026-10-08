import type { ScheduledCommand } from "../scene/source";
import { describeTime } from "./ClimateTime";
import { CLIMATE_RUN_S } from "./source";

const PERCENT = 100;

/** What a command does, in words: `heater 100%`, or `heater off`. */
export function describeCommand({ actuatorId, level }: ScheduledCommand): string {
  const name = actuatorId.replaceAll("_", " ");
  return level === 0 ? `${name} off` : `${name} ${Math.round(level * PERCENT)}%`;
}

/**
 * A climate run's schedule, its commands and the overrides made, under its
 * time slider: a marker on a bar over the run at each command's moment, and
 * each listed, to go to its moment or take it out. Those already applied at
 * the moment drawn are marked so.
 */
export function ClimateSchedule({
  schedule,
  time,
  onTime,
  onRemove,
}: {
  schedule: readonly ScheduledCommand[];
  time: number;
  onTime: (seconds: number) => void;
  onRemove: (index: number) => void;
}) {
  if (schedule.length === 0) {
    return null;
  }
  return (
    <section className="climate-schedule" aria-label="Schedule">
      <div className="climate-schedule-bar" aria-hidden="true">
        {schedule.map((command, index) => (
          <span
            // Commands are listed in the order given, so their places are theirs.
            // biome-ignore lint/suspicious/noArrayIndexKey: two commands may be alike.
            key={index}
            className={command.timeS <= time ? "applied" : "to-come"}
            style={{ left: `${(command.timeS / CLIMATE_RUN_S) * PERCENT}%` }}
          />
        ))}
      </div>
      <ol>
        {schedule.map((command, index) => {
          const said = `${describeCommand(command)} at ${describeTime(command.timeS)}`;
          return (
            // biome-ignore lint/suspicious/noArrayIndexKey: two commands may be alike.
            <li key={index} data-testid="schedule-command" data-applied={command.timeS <= time}>
              <button
                type="button"
                aria-label={`Go to ${said}`}
                onClick={() => onTime(command.timeS)}
              >
                {describeTime(command.timeS)}
              </button>{" "}
              {describeCommand(command)}{" "}
              <button type="button" aria-label={`Remove ${said}`} onClick={() => onRemove(index)}>
                ×
              </button>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
