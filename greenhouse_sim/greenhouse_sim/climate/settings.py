"""What a scenario's air starts from and exchanges with in a climate run
(P05.3): the outside, the air inside at the start, how much heat its glazing
passes, and how fast the air mixes.

Until weather comes (P07), the outside is one temperature for a whole run.
"""

from pydantic import BaseModel, ConfigDict, NonNegativeFloat, PositiveFloat


class ClimateSettings(BaseModel):
    """A scenario's outside, starting air, glazing and mixing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # The outside air's temperature, for the whole run.
    outside_temperature_c: float = 10.0
    # The air's temperature everywhere inside when the run starts.
    start_temperature_c: float = 18.0
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
