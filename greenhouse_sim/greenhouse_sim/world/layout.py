"""The greenhouse's layout: everything fixed inside its envelope.

Like the envelope (decision 0016), the layout is a description, given in the
greenhouse's frame, and its fixtures (`greenhouse_sim.world.fixtures`) are
generated from it. A scenario provides it today; a layout file or an editor
can provide it later, and the geometry follows. P02 grows it from fixtures
placed one by one to crop rows, their supports, walkways, zones, rails and
pipes.

Its crop rows (`greenhouse_sim.world.rows`) give the planting positions, where
plants can stand. A scenario's plants stand at them in order: the first plant
at the first row's first position, filling each row before the next.
"""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.envelope_checks import encloses, encloses_hull
from greenhouse_sim.world.fixtures import Fixture, Primitive
from greenhouse_sim.world.rows import CropRows, PlantingPosition


class Layout(BaseModel):
    """What stands inside a greenhouse, in metres, in its frame."""

    model_config = ConfigDict(frozen=True)

    # The crop's rows, and the planting positions along them.
    crop_rows: CropRows | None = None
    # Fixtures placed one by one, each described by a primitive.
    placed: list[Primitive] = []

    @model_validator(mode="after")
    def _every_fixture_has_its_own_identifier(self) -> Self:
        names = [fixture.fixture_id for fixture in self.fixtures()]
        repeated = sorted({name for name in names if names.count(name) > 1})
        if repeated:
            raise ValueError(f"fixtures share an identifier: {', '.join(repeated)}")
        return self

    def fixtures(self) -> list[Fixture]:
        """Every fixture the layout describes, in the greenhouse's frame: what
        carries its rows, then what is placed one by one."""
        rows = [] if self.crop_rows is None else self.crop_rows.fixtures()
        return rows + [fixture for primitive in self.placed for fixture in primitive.fixtures()]

    def planting_positions(self) -> list[PlantingPosition]:
        """Every planting position, row by row, in the greenhouse's frame."""
        return [] if self.crop_rows is None else self.crop_rows.planting_positions()


def outside_the_greenhouse(layout: Layout, envelope: Envelope) -> list[str]:
    """What of the layout does not fit inside the envelope: a fixture whose
    box reaches outside the space it encloses, or a planting position outside
    it."""
    fixtures = [
        fixture.fixture_id
        for fixture in layout.fixtures()
        if not encloses_hull(envelope, [(c.x, c.y, c.z) for c in fixture.corners()])
    ]
    positions = [
        position.position_id
        for position in layout.planting_positions()
        if not encloses(envelope, (position.point.x, position.point.y, position.point.z))
    ]
    return fixtures + positions
