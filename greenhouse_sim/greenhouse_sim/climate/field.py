"""The air as a scenario's equipment drives it: its `climate` field (P05.2).

The air's velocity is a base airflow, such as the scenario's own prescribed
pattern, plus what each running piece of its equipment adds through its
source terms (`greenhouse_sim.climate.sources`): for now, a fan's jet. Its
other quantities are the base airflow's, until the air's temperature and
humidity are carried (P05.3, P05.4).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np

from greenhouse_sim.airflow.contract import AirflowModel
from greenhouse_sim.climate.sources import SourceTerms, source_terms
from greenhouse_sim.domain.air import AirQuantity
from greenhouse_sim.fields.field import EnvironmentField, FieldGrid
from greenhouse_sim.world.equipment import Equipment


@dataclass(frozen=True, eq=False)
class ClimateAirflow:
    """A base airflow with equipment running in it, each piece at its level
    by actuator (off unless given), on a grid whose `solid` cells obstacles
    fill, in its order (z, y, x)."""

    base: AirflowModel
    equipment: Sequence[Equipment]
    levels: Mapping[str, float]
    solid: np.ndarray

    def terms(self, grid: FieldGrid) -> SourceTerms:
        """What the running equipment adds to the air over `grid`."""
        nx, ny, nz = grid.shape
        if self.solid.shape != (nz, ny, nx):
            raise ValueError(
                f"the solid cells are {self.solid.shape}, not the grid's {(nz, ny, nx)}"
            )
        terms = SourceTerms.none(grid)
        for piece in self.equipment:
            level = self.levels.get(piece.actuator_id, 0.0)
            terms = terms + source_terms(piece, level, grid, self.solid)
        return terms

    def field(self, field_id: str, grid: FieldGrid, time_s: float = 0.0) -> EnvironmentField:
        base = self.base.field(field_id, grid, time_s)
        channels = dict(base.channels)
        channels[AirQuantity.VELOCITY] = (
            base.channels[AirQuantity.VELOCITY] + self.terms(grid).velocity
        )
        return EnvironmentField(
            field_id=field_id,
            source=f"climate:{base.source}",
            grid=grid,
            time_s=time_s,
            channels=channels,
        )
