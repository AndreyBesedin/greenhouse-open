"""How the run gives a crop grown by area its drivers (P14.9, decision
0062): a driver profile, named and versioned.

A profile says, for each driver a model may declare
(`greenhouse_sim.biology.area_contract.Driver`), which quantity of the run
it gives in its place: the driver itself, or a substitute, which the
profile names; and its resolution, each driver's mean through a span of
it. A model declaring a driver the profile does not give is refused, saying
which, and so is a model whose step is not a whole number of the profile's
spans (decision 0064).

The first profile, `HOUSE_HOURS`, is the run as it is:

- **the whole house's air, hour by hour,** each hour's mean, a step's
  hours from its start
  (`WholeHouse.mean_between` over the hour), the same air every plant reads
  the day's mean of, so that a crop grown by area and one grown by plant
  live in one air;
- **its temperature standing for the canopy's:** the house has no canopy
  temperature, so a model driven by the canopy's is given the air's, and
  the profile says so;
- **the PAR above each scope's canopy,** each hour's mean
  (`greenhouse_sim.solar.scopes.ScopeLight`);
- **the CO₂ in the house's air.**

Air from the cells along a row is a later profile. A profile's name and
version are part of a run's identity, as its model's are: a model's
parameters name the profile it is driven through.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final

from greenhouse_sim.biology.area_contract import HourDrivers, StepCourse
from greenhouse_sim.climate.house import HouseAir
from greenhouse_sim.core.clock import steps_a_day
from greenhouse_sim.domain.crop import Driver
from greenhouse_sim.solar.scopes import ScopeLight
from greenhouse_sim.units import DAY_S, HOUR_S

# The house's mean air between two moments of a run, in seconds from its
# start (`WholeHouse.mean_between`).
type MeanAir = Callable[[float, float], HouseAir]


@dataclass(frozen=True)
class DriverProfile:
    """How the run gives a crop grown by area its drivers: its name and
    version; for each driver it gives, the quantity it gives in its place,
    itself or a substitute; and its resolution, the span each driver is the
    mean through, in seconds."""

    name: str
    version: int
    gives: Mapping[Driver, Driver]
    resolution_s: float

    def refusal(self, drivers: frozenset[Driver]) -> str | None:
        """Why the profile cannot drive a model that reads `drivers`, if it
        cannot: those it does not give."""
        missing = sorted(drivers - set(self.gives))
        if not missing:
            return None
        return f"the {self.name} drivers give no {', '.join(missing)}"

    def step_refusal(self, step_s: float) -> str | None:
        """Why the profile cannot drive a model of a step of `step_s`
        seconds, if it cannot: the step is not a whole number of its spans."""
        spans = round(step_s / self.resolution_s)
        if spans >= 1 and spans * self.resolution_s == step_s:
            return None
        return (
            f"the {self.name} drivers come {self.resolution_s:g} s at a time, "
            f"and a step of {step_s:g} s is not a whole number of them"
        )

    def substitutes(self, drivers: frozenset[Driver]) -> dict[Driver, Driver]:
        """The drivers of `drivers` it gives another quantity in place of,
        and which."""
        return {
            driver: given
            for driver in sorted(drivers)
            if (given := self.gives.get(driver)) is not None and given != driver
        }


HOUSE_HOURS: Final = DriverProfile(
    name="house_hours",
    version=1,
    gives={
        Driver.AIR_TEMPERATURE: Driver.AIR_TEMPERATURE,
        Driver.CANOPY_TEMPERATURE: Driver.AIR_TEMPERATURE,
        Driver.PAR_ABOVE: Driver.PAR_ABOVE,
        Driver.CO2: Driver.CO2,
    },
    resolution_s=HOUR_S,
)
# Each driver profile, by its name.
DRIVER_PROFILES: Final = {profile.name: profile for profile in (HOUSE_HOURS,)}


def house_hours(
    air: MeanAir, light: ScopeLight, *, step_s: float
) -> Callable[[int], dict[str, StepCourse]]:
    """Each scope's course on a step of the run, of `step_s` seconds, as
    `HOUSE_HOURS` gives it: the house's air through each of the step's
    hours, `air` its mean between two moments, and the PAR above the scope's
    canopy through each, as `light` reads it. Refused if the step is not a
    whole number of hours, or does not divide a day."""
    refused = HOUSE_HOURS.step_refusal(step_s)
    if refused is not None:
        raise ValueError(refused)
    steps_a_day(step_s)
    hours_a_step = round(step_s / HOUR_S)

    def courses(step: int) -> dict[str, StepCourse]:
        start = step * step_s
        day, first = int(start // DAY_S), round(start % DAY_S / HOUR_S)
        hours = [
            air(start + hour * HOUR_S, start + (hour + 1) * HOUR_S) for hour in range(hours_a_step)
        ]
        return {
            scope_id: StepCourse(
                hours=tuple(
                    HourDrivers(
                        temperature_c=mean.temperature_c,
                        par_above_umol_m2_s=par,
                        co2_ppm=mean.co2_ppm,
                    )
                    for mean, par in zip(hours, pars[first : first + hours_a_step], strict=True)
                )
            )
            for scope_id, pars in light.hours_par(day).items()
        }

    return courses
