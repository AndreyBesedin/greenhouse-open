"""The greenhouse's layout: everything fixed inside its envelope.

Like the envelope (decision 0016), the layout is a description, given in the
greenhouse's frame, and its fixtures (`greenhouse_sim.world.fixtures`) are
generated from it. A scenario provides it today; a layout file or an editor
can provide it later, and the geometry follows. P02 grows it from fixtures
placed one by one to crop rows, their supports, walkways, zones, rails and
pipes.
"""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.envelope_checks import encloses_hull
from greenhouse_sim.world.fixtures import Fixture, Primitive


class Layout(BaseModel):
    """What stands inside a greenhouse, in metres, in its frame."""

    model_config = ConfigDict(frozen=True)

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
        """Every fixture the layout describes, in the greenhouse's frame."""
        return [fixture for primitive in self.placed for fixture in primitive.fixtures()]


def fixtures_outside(layout: Layout, envelope: Envelope) -> list[str]:
    """The fixtures that do not fit inside the envelope: the box around one
    reaches outside the space it encloses."""
    return [
        fixture.fixture_id
        for fixture in layout.fixtures()
        if not encloses_hull(envelope, [(c.x, c.y, c.z) for c in fixture.corners()])
    ]
