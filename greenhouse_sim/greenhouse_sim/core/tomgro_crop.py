"""Reduced-State TOMGRO as a rung of the run's crop grown by area (P14.10,
decisions 0060 and 0062): `TomgroRung` keeps the contract of
`greenhouse_sim.biology.area_contract.AreaRung` for the model of
`greenhouse_sim.biology.tomato.tomgro`.

- **Its basis** is the greenhouse's floor: its states are per m² of it, as
  the model's are, for `ro` plants per m² of floor.
- **Its drivers** are the hours' air temperature, the PPFD above its canopy
  and the CO₂, the first hour's read for the day.
- **Its canopy's height,** where the light above it is read, is given: the
  model grows no height of its own.
"""

from typing import Final

from greenhouse_sim.biology.area_contract import DayCourse
from greenhouse_sim.biology.tomato.tomgro.growth import live_day
from greenhouse_sim.biology.tomato.tomgro.parameters import (
    INITIAL_STATE,
    TomgroParameters,
    TomgroState,
)
from greenhouse_sim.domain.crop import Driver
from greenhouse_sim.domain.scopes import AreaBasis

# What the model reads of each hour.
DRIVERS: Final = frozenset({Driver.AIR_TEMPERATURE, Driver.PAR_ABOVE, Driver.CO2})


class TomgroRung:
    """Reduced-State TOMGRO with `parameters`, its canopy `canopy_height_m`
    above its planting positions: see the module."""

    def __init__(self, parameters: TomgroParameters, canopy_height_m: float) -> None:
        self.parameters = parameters
        self._canopy_height_m = canopy_height_m

    @property
    def state_type(self) -> type[TomgroState]:
        return TomgroState

    @property
    def basis(self) -> AreaBasis:
        return AreaBasis.FLOOR

    @property
    def drivers(self) -> frozenset[Driver]:
        return DRIVERS

    @property
    def canopy_height_m(self) -> float:
        return self._canopy_height_m

    def planted(self) -> TomgroState:
        return INITIAL_STATE

    def live_day(self, state: TomgroState, course: DayCourse) -> TomgroState:
        return live_day(state, course.hours, self.parameters)
