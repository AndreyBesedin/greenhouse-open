"""Vanthoor's model as a rung of the run's crop grown by area (P14.10,
decisions 0060 and 0062): `VanthoorRung` keeps the contract of
`greenhouse_sim.biology.area_contract.AreaRung` for the model of
`greenhouse_sim.biology.tomato.vanthoor`.

- **Its basis** is the greenhouse's floor: its states are per m² of it, as
  the model's are.
- **Its drivers** are the canopy's temperature, the PAR above its canopy and
  the CO₂. A driver profile may give the air's temperature in the canopy's
  place, and says so (`greenhouse_sim.core.drivers`).
- **Its step** is an hour (decision 0064), since its state moves within the
  day. An hour's drivers, each the mean through it, are held through it,
  where its reference's run straight between hourly moments. What that
  changes is measured (`greenhouse_sim/tests/test_vanthoor.py`).
- **Its canopy's height,** where the light above it is read, is given: the
  model grows no height of its own.
"""

from typing import Final

from greenhouse_sim.biology.area_contract import StepCourse
from greenhouse_sim.biology.tomato.vanthoor.growth import live_hour
from greenhouse_sim.biology.tomato.vanthoor.parameters import (
    INITIAL_STATE,
    VanthoorParameters,
    VanthoorState,
)
from greenhouse_sim.domain.crop import Driver
from greenhouse_sim.domain.scopes import AreaBasis
from greenhouse_sim.units import HOUR_S

# What the model reads of each hour.
DRIVERS: Final = frozenset({Driver.CANOPY_TEMPERATURE, Driver.PAR_ABOVE, Driver.CO2})


class VanthoorRung:
    """Vanthoor's model with `parameters`, its canopy `canopy_height_m` above
    its planting positions: see the module."""

    def __init__(self, parameters: VanthoorParameters, canopy_height_m: float) -> None:
        self.parameters = parameters
        self._canopy_height_m = canopy_height_m

    @property
    def step_s(self) -> float:
        return HOUR_S

    @property
    def state_type(self) -> type[VanthoorState]:
        return VanthoorState

    @property
    def basis(self) -> AreaBasis:
        return AreaBasis.FLOOR

    @property
    def drivers(self) -> frozenset[Driver]:
        return DRIVERS

    @property
    def canopy_height_m(self) -> float:
        return self._canopy_height_m

    def planted(self) -> VanthoorState:
        return INITIAL_STATE

    def live_step(self, state: VanthoorState, course: StepCourse) -> VanthoorState:
        for hour in course.hours:
            state = live_hour(state, hour, hour, self.parameters)
        return state
