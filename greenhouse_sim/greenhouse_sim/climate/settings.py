"""What a scenario's air starts from in a climate run, and how it exchanges
with the outside (P05.3, P05.4, P06.2, P07.5): the air inside at the start,
how much heat its glazing passes, how much air leaks through it, and how
fast the air mixes. The outside itself is the scenario's weather
(`greenhouse_sim.weather`, P07.1).

They are the parameters of the house air's two models (P14.6): the whole
house alone (`WholeHouseAir`), and the air cell by cell beside it
(`GridAir`), which mixes too.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveFloat

from greenhouse_sim.climate.glazing import most_u_w_m2k
from greenhouse_sim.units import HOUR_S

type Percent = Annotated[float, Field(ge=0.0, le=100.0)]


class HouseSettings(BaseModel):
    """A scenario's starting air, glazing and infiltration: what the whole
    house's air is worked out from (`greenhouse_sim.climate.house`)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # The air's temperature and relative humidity everywhere inside when the
    # run starts.
    start_temperature_c: float = 18.0
    start_humidity_pct: Percent = 75.0
    start_co2_ppm: PositiveFloat = 420.0
    # How much heat the walls' and roof's glazing passes, per square metre and
    # per kelvin between inside and out, in a 4 m/s wind: about 6 W/m²K for
    # single glass. The wind sets it at every other moment
    # (`climate.glazing`). Zero shuts the house off from the outside.
    glazing_u_w_m2k: Annotated[float, Field(ge=0.0, lt=most_u_w_m2k())] = 6.0
    # How much of the house's air leaks out through a shut house's gaps each
    # hour, and is replaced by the outside's: a share in still air, and as
    # much again for every so many metres a second of wind, typical of a
    # well-kept glasshouse (P07.5). Zero for both seals it.
    infiltration_per_h: NonNegativeFloat = 0.25
    infiltration_per_h_per_m_s: NonNegativeFloat = 0.1

    def infiltration_per_s(self, wind_m_s: float) -> float:
        """The share of the house's air that leaks out each second in a wind,
        replaced by the outside's."""
        return (self.infiltration_per_h + self.infiltration_per_h_per_m_s * wind_m_s) / HOUR_S


class ClimateSettings(HouseSettings):
    """A scenario's starting air, glazing, infiltration and mixing: what a
    climate run's air is worked out from, the whole house's and cell by
    cell (`greenhouse_sim.climate.run`)."""

    # The air's effective diffusivity: its own, about 2e-5 m²/s, with the
    # mixing its half-metre cells cannot resolve and the convection a climate
    # run does not carry folded in. At 0.1 m²/s a small house's air mixes
    # across in minutes, as heating's own convection mixes it, and a heater's
    # corner stays some tens of degrees warmer, not a hundred.
    mixing_m2_s: PositiveFloat = 0.1


class GridAir(ClimateSettings):
    """The house's air cell by cell, on the field's grid, beside the whole
    house's (`greenhouse_sim.climate.day`): the house air's model that draws
    where its air is warm, damp or still, its parameters a climate run's."""

    kind: Literal["grid"] = "grid"

    def run_settings(self) -> ClimateSettings:
        """What its climate run works its air out from: its own."""
        return ClimateSettings.model_validate(self.model_dump(exclude={"kind"}))


class WholeHouseAir(HouseSettings):
    """The whole house's air alone, one well-mixed volume, which the run
    draws the same in every cell (`greenhouse_sim.climate.day`): the house
    air's model that works out no air cell by cell, so none of a grid's
    mixing."""

    kind: Literal["whole_house"] = "whole_house"

    def run_settings(self) -> ClimateSettings:
        """What its climate run works its air out from: its own, and the
        grid's default mixing, which none of its air is worked out with."""
        return ClimateSettings.model_validate(self.model_dump(exclude={"kind"}))
