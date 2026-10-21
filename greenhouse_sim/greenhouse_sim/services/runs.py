"""A run as a client asks for it, and its moments as the services check
them (P09.2): from its start to the end of its scenario's last day, on the
run's clock (`greenhouse_sim.core.clock`)."""

from collections.abc import Mapping
from dataclasses import dataclass, field

from greenhouse_sim.core.clock import day_start
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.services.errors import InvalidRequest

# A command as a request writes it: its moment, its actuator and its level.
type Commanded = tuple[float, str, float]


@dataclass(frozen=True)
class RunRequest:
    """A scenario's run as a client asks for it (audit W11, `AUDIT.6`), read
    once by the API and taken by every service that runs one:

    - its scenario, one of its layouts and a weather, each by name, or its
      own when None;
    - its equipment's levels and its doors' and vents' openings from the
      start, by identifier;
    - its commands, in the order given, those at one moment included;
    - its daily commands, or None for its scenario's own: apart from an
      empty tuple, which is none at all.

    It names a run, and nothing of what is asked of it: the moment drawn and
    a series' window are the services' own arguments, so the runs kept are
    told apart without them. Each service checks it as it always has: a
    layout, a weather or a piece of equipment the scenario does not have is
    refused there, not here."""

    scenario_id: str
    layout: str | None = None
    weather: str | None = None
    levels: Mapping[str, float] = field(default_factory=dict)
    openings: Mapping[str, float] = field(default_factory=dict)
    commands: tuple[Commanded, ...] = ()
    daily: tuple[Commanded, ...] | None = None
    # Its target changes (#274), as a request writes them: each its moment,
    # its target and the value it sets, in °C.
    targets: tuple[Commanded, ...] = ()


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
