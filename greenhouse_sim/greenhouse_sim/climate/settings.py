"""What a scenario's air starts from and exchanges with in a climate run
(P05.3, P05.4): the outside, the air inside at the start, how much heat its
glazing passes, and how fast the air mixes.

Until weather comes (P07), the outside is one temperature and humidity for a
whole run.
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, PositiveFloat

type Percent = Annotated[float, Field(ge=0.0, le=100.0)]


class ClimateSettings(BaseModel):
    """A scenario's outside, starting air, glazing and mixing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # The outside air's temperature and relative humidity, for the whole run.
    outside_temperature_c: float = 10.0
    outside_humidity_pct: Percent = 80.0
    # The air's temperature and relative humidity everywhere inside when the
    # run starts.
    start_temperature_c: float = 18.0
    start_humidity_pct: Percent = 75.0
    # How much heat the walls' and roof's glazing passes, per square metre and
    # per kelvin between inside and out: about 6 W/m²K for single glass. Zero
    # shuts the house off from the outside.
    glazing_u_w_m2k: NonNegativeFloat = 6.0
    # The air's effective diffusivity: its own, about 2e-5 m²/s, with the
    # mixing its half-metre cells cannot resolve and the convection a climate
    # run does not carry folded in. At 0.1 m²/s a small house's air mixes
    # across in minutes, as heating's own convection mixes it, and a heater's
    # corner stays some tens of degrees warmer, not a hundred.
    mixing_m2_s: PositiveFloat = 0.1
