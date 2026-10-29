"""What the run needs from a model of its crop grown by area (P14.9,
decision 0062).

A model of the crop grown by area grows a canopy per m² of ground, with no
plants, organs or crowns of its own. Each instance of it is the model on a
scope (`greenhouse_sim.world.scopes.CropScope`): its state is per m² of the
area its model declares its quantities per (`basis`), and the run keeps it
beside each scope's (`greenhouse_sim.core.area_crop.AreaCrop`).

- **Its drivers** are declared (`drivers`): the quantities it reads, hour by
  hour, each the mean through its hour. The run gives them through a driver
  profile, named and versioned, which says how it provides each and what it
  substitutes (`greenhouse_sim.core.drivers`).
- **The light it is given** is the PAR above its canopy, incident: how much
  of it the canopy absorbs, through its leaf area, is the model's. It is
  read at the canopy's height (`canopy_height_m`), which its parameters
  give, since it grows no height of its own.
- **A day at a time:** the run gives an instance its day's course, its
  drivers hour by hour from the day's start, and keeps what it returns, as
  it keeps a plant's day (`greenhouse_sim.core.crop_days`).

`greenhouse_sim/tests/test_area_crop.py` holds every model of it to the
rules of `AreaRung`.
"""

from typing import Annotated, Protocol

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat

from greenhouse_sim.domain.crop import Driver
from greenhouse_sim.domain.scopes import AreaBasis
from greenhouse_sim.units import HOURS_A_DAY


class HourDrivers(BaseModel):
    """One hour of what a scope's crop is driven by, each quantity its mean
    through the hour: its temperature, which stands for the drivers its
    profile says, the PAR above its canopy, and the CO₂."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    temperature_c: float
    par_above_umol_m2_s: NonNegativeFloat
    co2_ppm: NonNegativeFloat


class DayCourse(BaseModel):
    """A scope's day, hour by hour from its start: what a crop grown by area
    lives it in."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    hours: Annotated[tuple[HourDrivers, ...], Field(min_length=HOURS_A_DAY, max_length=HOURS_A_DAY)]


class AreaRung[StateT: BaseModel](Protocol):
    """A model of the run's crop grown by area, a rung of the crop part's
    ladder (decision 0035) beside the per-plant ones (`CropRung`): how it
    starts a scope's canopy and lives it a day at a time, per m² of its
    basis. The run gives each instance its day's course and keeps the
    states; a rung keeps nothing of them. A rung must:

    - start a canopy, and live its day, the same every time it is given the
      same state and course, whatever other scopes grow beside it;
    - leave the state it is given as it was, returning another;
    - grow the same per m² on two scopes given the same course, whatever
      their areas;
    - keep its states as values that survive a JSON round trip as its
      `state_type`, so that a checkpoint keeps them."""

    @property
    def state_type(self) -> type[StateT]:
        """What its states are, as a checkpoint reads them back."""
        ...

    @property
    def basis(self) -> AreaBasis:
        """The area its quantities are per m² of."""
        ...

    @property
    def drivers(self) -> frozenset[Driver]:
        """The quantities it reads, each hour's mean."""
        ...

    @property
    def canopy_height_m(self) -> float:
        """How high above its planting positions the light above its canopy
        is read, in m."""
        ...

    def planted(self) -> StateT:
        """Its canopy, per m² of its basis, as the run's first day finds
        it."""
        ...

    def live_day(self, state: StateT, course: DayCourse) -> StateT:
        """Its canopy once it has lived a day of `course`."""
        ...
