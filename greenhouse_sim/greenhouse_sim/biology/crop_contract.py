"""What the run needs from a model of its crop (P14.3, decision 0035).

A model of the run's crop is a rung of the crop part's ladder: it lives one
plant a day at a time in what the run gives it (`LocalEnvironment`,
decision 0024), and carries crop work out on it; the run keeps the plants
(`greenhouse_sim.core.crop.RunCrop`). Its rules are `CropRung`'s, and
`greenhouse_sim/tests/test_crop_rungs.py` holds every rung to them.
"""

from typing import Protocol

from greenhouse_sim.biology.plant.environment import LocalEnvironment
from greenhouse_sim.core.crop_actions import CarriedOut, CropAction
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.training import Training


class CropPlant(Protocol):
    """A plant of the run's crop, as any of its models keeps it: known by
    its identifier."""

    @property
    def plant_id(self) -> str: ...


class CropRung[PlantT: CropPlant](Protocol):
    """A model of the run's crop, a rung of the crop part's ladder (decision
    0035): how it starts a plant, lives it a day at a time and carries crop
    work out on it. The run gives each plant its day (`LocalEnvironment`,
    decision 0024) and keeps the plants; a rung keeps nothing of them. A
    rung must:

    - start a plant, and live its day, the same every time it is given the
      same plant and environment, whatever other plants live beside it:
      its draws are seeded by the plant's identity and the scenario's seed;
    - leave the plant it is given as it was, returning another;
    - keep the plant's identifier through every day and every action;
    - keep its plants as values that survive a JSON round trip as its
      `plant_type`, so that a checkpoint keeps them.

    `greenhouse_sim/tests/test_crop_rungs.py` holds every rung to them."""

    @property
    def plant_type(self) -> type[PlantT]:
        """What its plants are, as a checkpoint reads them back."""
        ...

    def transplant(self, plant_id: str) -> PlantT:
        """The plant `plant_id` as the run's first day finds it."""
        ...

    def live_day(self, plant: PlantT, environment: LocalEnvironment) -> PlantT:
        """The plant once it has lived a day in `environment`."""
        ...

    def carry_out(
        self, plant: PlantT, action: CropAction, training: Training | None
    ) -> CarriedOut[PlantT]:
        """A crop action carried out on the plant, trained as `training`
        says, or straight along its row and hanging from no wire if it is
        not given: done with its effect, or refused, saying why."""
        ...

    def crown(self, plant: PlantT, training: Training) -> tuple[Vector3, float]:
        """Where its crown rises from, in its training's frame from its
        foot, and how tall it stands, in m."""
        ...

    def recorded(self, plant: PlantT) -> int:
        """How many events its history holds: where a day's crop work ends,
        before the run's own crop actions (`StepWork`); none if it keeps no
        history."""
        ...
