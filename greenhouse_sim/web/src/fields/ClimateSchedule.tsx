import { DAY_S, dayStart, runDay } from "../clock";
import { latestDaily, type ScheduledCommand } from "../scene/source";
import { PERCENT } from "../units";
import { describeTime } from "./ClimateTime";

/** What a command does, in words: `heater 100%`, or `heater off`. */
export function describeCommand({ actuatorId, level }: ScheduledCommand): string {
  const name = actuatorId.replaceAll("_", " ");
  return level === 0 ? `${name} off` : `${name} ${Math.round(level * PERCENT)}%`;
}

/** The commands a run gives next after a moment, up to its end: all those at
 * the soonest moment still to come, a daily one's its next time of day, in
 * the order the run gives them, its daily ones first. None once it has none
 * left to give. */
function nextCommands(
  schedule: readonly ScheduledCommand[],
  daily: readonly ScheduledCommand[],
  time: number,
  end: number,
): ScheduledCommand[] {
  const coming = [
    // The simulator gives a daily command once on each of the run's days, at
    // its time of day after that day's midnight (`DailyCommand.through`): the
    // last on the last day, so never at the run's end, as a midnight one
    // would be. A command for a moment may come at the end itself.
    ...daily.flatMap((command) => {
      const latest = latestDaily(command, time);
      const timeS = latest === null ? command.timeS : latest + DAY_S;
      return timeS < end ? [{ ...command, timeS }] : [];
    }),
    ...schedule.filter((command) => command.timeS <= end),
  ].filter((command) => command.timeS > time);
  const soonest = Math.min(...coming.map((command) => command.timeS));
  return coming.filter((command) => command.timeS === soonest);
}

/** A schedule folded to a line: how many commands it has, and which it gives
 * next, if any are still to come before its run ends. */
export function describeSchedule({
  schedule,
  daily,
  time,
  days,
}: {
  schedule: readonly ScheduledCommand[];
  daily: readonly ScheduledCommand[];
  time: number;
  days: number;
}): string {
  const count = schedule.length + daily.length;
  const counted = `Schedule: ${count} ${count === 1 ? "command" : "commands"}`;
  const [first, ...more] = nextCommands(schedule, daily, time, days * DAY_S);
  if (first === undefined) {
    return `${counted}, none to come.`;
  }
  const others = more.length === 0 ? "" : ` and ${more.length} more`;
  return `${counted}. Next at ${describeTime(first.timeS)}: ${describeCommand(first)}${others}.`;
}

/**
 * A climate run's schedule, its commands and the overrides made, and its
 * daily commands, under its time sliders. It folds, as the timeline and the
 * checkpoints do, so that a scenario's many daily commands do not push the
 * panels below it away: to a line saying how many commands it has and which
 * comes next, over a bar across the moment's day with a marker at each of
 * that day's commands, the daily ones' among them. Opened, it lists every
 * command, to go to its moment, repeat it every day, or take it out. Those
 * already applied at the moment drawn are marked so.
 */
export function ClimateSchedule({
  schedule,
  daily = [],
  time,
  days,
  onTime,
  onRemove,
  onRepeat,
  onRemoveDaily,
}: {
  schedule: readonly ScheduledCommand[];
  /** Commands every day, each `timeS` its time of day. */
  daily?: readonly ScheduledCommand[];
  time: number;
  /** How many days the run lasts: no command comes after its end. */
  days: number;
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
      <details>
        <summary>
          <span data-testid="schedule-summary">
            {describeSchedule({ schedule, daily, time, days })}
          </span>
          <span className="climate-schedule-bar" aria-hidden="true">
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
          </span>
        </summary>
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
      </details>
    </section>
  );
}
