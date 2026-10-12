import { DAY_S, dayStart, runDay } from "../clock";
import type { ScheduledCommand } from "../scene/source";
import { describeTime } from "./ClimateTime";

const PERCENT = 100;

/** What a command does, in words: `heater 100%`, or `heater off`. */
export function describeCommand({ actuatorId, level }: ScheduledCommand): string {
  const name = actuatorId.replaceAll("_", " ");
  return level === 0 ? `${name} off` : `${name} ${Math.round(level * PERCENT)}%`;
}

/**
 * A climate run's schedule, its commands and the overrides made, and its
 * daily commands, under its time sliders: a marker on a bar over the
 * moment's day at each of that day's commands, the daily ones' among them,
 * and every command listed, to go to its moment, repeat it every day, or
 * take it out. Those already applied at the moment drawn are marked so.
 */
export function ClimateSchedule({
  schedule,
  daily = [],
  time,
  onTime,
  onRemove,
  onRepeat,
  onRemoveDaily,
}: {
  schedule: readonly ScheduledCommand[];
  /** Commands every day, each `timeS` its time of day. */
  daily?: readonly ScheduledCommand[];
  time: number;
  onTime: (seconds: number) => void;
  onRemove: (index: number) => void;
  /** One of the commands repeated every day, in its place. */
  onRepeat?: (index: number) => void;
  onRemoveDaily?: (index: number) => void;
}) {
  if (schedule.length === 0 && daily.length === 0) {
    return null;
  }
  const day = runDay(time);
  const from = dayStart(time);
  // The day's moments of its commands, and of its daily ones.
  const marked = [
    ...daily.map((command) => ({ ...command, timeS: from + command.timeS, every: true })),
    ...schedule
      .filter((command) => runDay(command.timeS) === day)
      .map((command) => ({ ...command, every: false })),
  ];
  return (
    <section className="climate-schedule" aria-label="Schedule">
      <div className="climate-schedule-bar" aria-hidden="true">
        {marked.map((command, index) => (
          <span
            // Commands are listed in the order given, so their places are theirs.
            // biome-ignore lint/suspicious/noArrayIndexKey: two commands may be alike.
            key={index}
            data-testid="schedule-marker"
            className={`${command.timeS <= time ? "applied" : "to-come"}${command.every ? " daily" : ""}`}
            style={{ left: `${((command.timeS - from) / DAY_S) * PERCENT}%` }}
          />
        ))}
      </div>
      <ol>
        {daily.map((command, index) => {
          const said = `${describeCommand(command)} every day at ${describeTime(command.timeS)}`;
          const today = from + command.timeS;
          return (
            // biome-ignore lint/suspicious/noArrayIndexKey: two commands may be alike.
            <li key={`daily-${index}`} data-testid="daily-command" data-applied={today <= time}>
              <button type="button" aria-label={`Go to ${said}`} onClick={() => onTime(today)}>
                every day {describeTime(command.timeS)}
              </button>{" "}
              {describeCommand(command)}{" "}
              <button
                type="button"
                aria-label={`Remove ${said}`}
                onClick={() => onRemoveDaily?.(index)}
              >
                ×
              </button>
            </li>
          );
        })}
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
              {onRepeat !== undefined && (
                <button
                  type="button"
                  aria-label={`Repeat ${said} every day`}
                  onClick={() => onRepeat(index)}
                >
                  ↻
                </button>
              )}{" "}
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
