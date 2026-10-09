"""What a scenario's air starts from in a climate run, and how it exchanges
with the outside (P05.3, P05.4, P06.2, P07.5): the air inside at the start,
how much heat its glazing passes, how much air leaks through it, and how
fast the air mixes. The outside
itself is the scenario's weather (`greenhouse_sim.weather`, P07.1).
"""

from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveFloat

from greenhouse_sim.climate.glazing import most_u_w_m2k

type Percent = Annotated[float, Field(ge=0.0, le=100.0)]

SECONDS_PER_HOUR: Final = 3600.0


class ClimateSettings(BaseModel):
    """A scenario's starting air, glazing, infiltration and mixing."""

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
    # The air's effective diffusivity: its own, about 2e-5 m²/s, with the
    # mixing its half-metre cells cannot resolve and the convection a climate
    # run does not carry folded in. At 0.1 m²/s a small house's air mixes
    # across in minutes, as heating's own convection mixes it, and a heater's
    # corner stays some tens of degrees warmer, not a hundred.
    mixing_m2_s: PositiveFloat = 0.1
    # How much of the house's air leaks out through a shut house's gaps each
    # hour, and is replaced by the outside's: a share in still air, and as
    # much again for every so many metres a second of wind, typical of a
    # well-kept glasshouse (P07.5). Zero for both seals it.
    infiltration_per_h: NonNegativeFloat = 0.25
    infiltration_per_h_per_m_s: NonNegativeFloat = 0.1

    def infiltration_per_s(self, wind_m_s: float) -> float:
        """The share of the house's air that leaks out each second in a wind,
        replaced by the outside's."""
        return (
            self.infiltration_per_h + self.infiltration_per_h_per_m_s * wind_m_s
        ) / SECONDS_PER_HOUR
