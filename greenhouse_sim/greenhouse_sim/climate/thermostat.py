"""A thermostat on a scenario's heater (P10.3): it heats the house's air to a
setpoint, one by day and a lower one by night, switching its heater full on
when the air falls below the setpoint by half its band and off when it rises
above it by as much, and leaving it as it is between. A climate computer's
simplest heating, it runs its heater as long as the weather needs: all night
in a cold spell, now and then on a mild night, not at all on a warm one.

It follows the house's mean air (`climate.house`), the air its sensors
sample, and switches its heater the moment that air reaches its band's edge,
as a thermostat that senses the air all the time does; the grid run's air
follows its switching (`climate.run`). Its day and night are times of a
run's day, on the minute, as daily commands' are (`climate.commands`). A
command to its heater, from the start or later, takes the heater out of its
hands from that moment: the heater is then where the commands put it. Its
setpoints are a run's targets, which a run may change from a moment on
(`climate.commands`, #274): the latest change to its day's or its night's
setpoint holds from then on.
"""

from collections.abc import Mapping
from typing import Annotated, Final, Self

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, model_validator

from greenhouse_sim.core.clock import DAY_S
from greenhouse_sim.domain.equipment import Target
from greenhouse_sim.units import HOUR_S

# Its day and night start on the minute, where a run's air is worked from.
MINUTE_S: Final = 60.0
# A heater a thermostat runs is full on or off.
ON: Final = 1.0
OFF: Final = 0.0

type TimeOfDay = Annotated[float, Field(ge=0.0, lt=DAY_S)]


class Thermostat(BaseModel):
    """Heat the house's air to `day_c` from `day_from_s` and to `night_c`
    from `night_from_s`, times of a run's day, with the heater `actuator_id`,
    on below the setpoint by half `band_c` and off above it by as much."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    actuator_id: str
    day_c: float
    night_c: float
    day_from_s: TimeOfDay = 7 * HOUR_S
    night_from_s: TimeOfDay = 19 * HOUR_S
    band_c: PositiveFloat = 1.0

    @model_validator(mode="after")
    def _a_day_between_two_nights(self) -> Self:
        if not self.day_from_s < self.night_from_s:
            raise ValueError("a thermostat's day starts before its night, in a run's day")
        if self.day_from_s % MINUTE_S or self.night_from_s % MINUTE_S:
            raise ValueError("a thermostat's day and night start on the minute")
        return self

    def setpoints_c(self, targets: Mapping[Target, float] | None = None) -> tuple[float, float]:
        """Its setpoints by day and by night, as a run's `targets` in force
        have changed them."""
        changed = targets or {}
        return (
            changed.get(Target.HEATING_DAY, self.day_c),
            changed.get(Target.HEATING_NIGHT, self.night_c),
        )

    def setpoint_c(self, time_s: float, targets: Mapping[Target, float] | None = None) -> float:
        """The temperature it heats to at `time_s`, a moment of a run, its
        setpoints as `targets` in force then have changed them."""
        day_c, night_c = self.setpoints_c(targets)
        of_day = time_s % DAY_S
        return day_c if self.day_from_s <= of_day < self.night_from_s else night_c

    def heats(
        self,
        temperature_c: float,
        heating: bool,
        time_s: float,
        targets: Mapping[Target, float] | None = None,
    ) -> bool:
        """Whether it runs its heater from `time_s` on, the air being at
        `temperature_c` then and the heater on or not until then, its
        setpoints as `targets` in force then have changed them."""
        setpoint = self.setpoint_c(time_s, targets)
        if temperature_c < setpoint - self.band_c / 2:
            return True
        if temperature_c > setpoint + self.band_c / 2:
            return False
        return heating
