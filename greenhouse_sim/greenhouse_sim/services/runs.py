"""A run's moments, as the services check them (P09.2): from its start to
the end of its scenario's last day, on the run's clock
(`greenhouse_sim.core.clock`)."""

from greenhouse_sim.core.clock import day_start
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.services.errors import InvalidRequest


def checked_moment(config: ScenarioConfig, time_s: float) -> float:
    """A moment of a scenario's run, refused if the run does not reach it."""
    length = config.run_length_s()
    if not 0.0 <= time_s <= length:
        raise InvalidRequest(
            f"a run of {config.greenhouse_id} lasts from 0 to {length:.15g} s, its "
            f"{config.duration_days} days, not {time_s:.15g}"
        )
    return time_s


def checked_window(config: ScenarioConfig, from_s: float | None, until_s: float) -> float:
    """Where a series up to `until_s` begins: at `from_s` if asked, or else
    at the start of the day `until_s` belongs to, so that a series is a
    day's at most unless a longer one is asked for. Refused if `until_s` or
    `from_s` lies outside the run, or `from_s` after `until_s`."""
    checked_moment(config, until_s)
    if from_s is None:
        return day_start(until_s)
    checked_moment(config, from_s)
    if from_s > until_s:
        raise InvalidRequest(
            f"a series runs from {from_s:.15g} s to no earlier, not {until_s:.15g}"
        )
    return from_s
