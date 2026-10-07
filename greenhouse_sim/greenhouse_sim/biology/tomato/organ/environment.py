"""What a plant takes from where it stands, and how it responds.

A plant lives its days one at a time, each in its local environment: the
day's mean air temperature, its daily light integral of photosynthetically
active radiation (PAR), the CO₂ concentration and the root zone's water
status. Anything that can say what one plant experienced on one day serves
as its environment (`Environment`): the lab's presets today, the
greenhouse's climate and its spatial fields later.

The responses are simple first ones; physiological realism comes later.
Temperature sets the pace of development through thermal time. Light, CO₂
and water set how much of their potential growth the plant's organs make
that day, as a growth factor from 0 to 1: the product of a saturating
response to light, a saturating response to CO₂, and the water status
itself, each 1 at the reference conditions or better. The crop's sizes are
its potential, reached under the reference conditions; the environment only
ever holds growth back.
"""

from typing import Annotated, Protocol

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveFloat


class LocalEnvironment(BaseModel):
    """What one plant experiences over one day, where it stands."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mean_temperature_c: float
    # The day's light integral of photosynthetically active radiation.
    par_mol_m2_day: NonNegativeFloat
    co2_ppm: NonNegativeFloat
    # The root zone's water status: 1 well watered, 0 too dry to grow.
    water_status: Annotated[float, Field(ge=0, le=1)] = 1.0


class Environment(Protocol):
    """Anything that can say what each plant experiences on each day."""

    def local(self, plant_id: str, day: int) -> LocalEnvironment:
        """What the plant experiences on this day."""
        ...


class ResponseParams(BaseModel):
    """How growth responds to light and CO₂, saturating towards the reference
    conditions, at which a plant makes all of its potential growth."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reference_par_mol_m2_day: PositiveFloat = 25.0
    reference_co2_ppm: PositiveFloat = 800.0
    # The light and CO₂ at which each response is half its saturated value.
    par_half_saturation_mol_m2_day: PositiveFloat = 10.0
    co2_half_saturation_ppm: PositiveFloat = 300.0


def _saturating(value: float, half: float) -> float:
    return value / (value + half)


def light_response(par_mol_m2_day: float, params: ResponseParams) -> float:
    """The share of potential growth a day's light allows."""
    reference = _saturating(params.reference_par_mol_m2_day, params.par_half_saturation_mol_m2_day)
    return min(1.0, _saturating(par_mol_m2_day, params.par_half_saturation_mol_m2_day) / reference)


def co2_response(co2_ppm: float, params: ResponseParams) -> float:
    """The share of potential growth a day's CO₂ allows."""
    reference = _saturating(params.reference_co2_ppm, params.co2_half_saturation_ppm)
    return min(1.0, _saturating(co2_ppm, params.co2_half_saturation_ppm) / reference)


def growth_factor(environment: LocalEnvironment, params: ResponseParams) -> float:
    """The share of their potential growth a plant's organs make on a day in
    this environment: light's, CO₂'s and water's shares together."""
    return (
        light_response(environment.par_mol_m2_day, params)
        * co2_response(environment.co2_ppm, params)
        * environment.water_status
    )
