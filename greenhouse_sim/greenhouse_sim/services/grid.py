"""The grid a scenario's fields cover: its greenhouse's air under the
gutters, from its floor's front right corner up to its eaves, in cells at
most `CELL_M` wide."""

from typing import Final

from greenhouse_sim.fields.field import FieldGrid
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world.geometry import Vector3

# The widest a field's cell may be, in metres.
CELL_M: Final = 0.5


def air_grid(config: ScenarioConfig) -> FieldGrid:
    """The grid over a scenario's greenhouse's air under the gutters, as it
    is configured."""
    envelope = config.envelope
    return FieldGrid.over(
        Vector3(x=0.0, y=0.0, z=0.0),
        Vector3(x=envelope.length, y=envelope.width, z=envelope.eave_height),
        CELL_M,
    )
