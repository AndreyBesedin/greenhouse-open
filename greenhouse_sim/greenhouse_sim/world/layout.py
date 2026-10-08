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

Its climate equipment (`greenhouse_sim.world.equipment`), fans, heaters and
dehumidifiers, stands among the fixtures: what of it is in the way of air or
robots is among the layout's obstructions, and kept off its walkways. Its
sensors and cameras (`greenhouse_sim.world.sensors`) stand there too, in the
way of nothing.

Walkways, service zones and keep-out volumes (`greenhouse_sim.world.zones`)
are kept clear of planting: no position lies inside one, and the rows'
supports stop short of them. Walkways stay clear of anything that obstructs
movement below `WALKWAY_HEADROOM_M`; a layout that puts such a fixture on
one is refused. Above it, pipes may cross a walkway.
"""

from collections import Counter
from typing import Final, Self

from pydantic import BaseModel, ConfigDict, model_validator

from greenhouse_sim.domain.layout import Obstruction
from greenhouse_sim.world.envelope import Envelope
from greenhouse_sim.world.envelope_checks import encloses, encloses_hull
from greenhouse_sim.world.equipment import Equipment
from greenhouse_sim.world.fixtures import Fixture, Primitive, WalkwayPrimitive
from greenhouse_sim.world.geometry import Vector3
from greenhouse_sim.world.rows import CropRows, PlantingPosition
from greenhouse_sim.world.sensors import Sensor
from greenhouse_sim.world.zones import Strip, Zone

# Walkways stay clear up to this height: a doorway's.
WALKWAY_HEADROOM_M: Final = 2.1


class Layout(BaseModel):
    """What stands inside a greenhouse, in metres, in its frame."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # The crop's rows, and the planting positions along them.
    crop_rows: CropRows | None = None
    # Fixtures placed one by one, each described by a primitive. Walkways
    # among them are kept clear.
    placed: list[Primitive] = []
    # Service zones and keep-out volumes.
    zones: list[Zone] = []
    # Climate equipment: fans, heaters and dehumidifiers.
    equipment: list[Equipment] = []
    # Sensors and cameras.
    sensors: list[Sensor] = []

    @model_validator(mode="after")
    def _every_fixture_and_zone_has_its_own_identifier(self) -> Self:
        names = Counter(
            [fixture.fixture_id for fixture in self.fixtures()]
            + [zone.zone_id for zone in self.zones]
            + [piece.actuator_id for piece in self.equipment]
            + [sensor.sensor_id for sensor in self.sensors]
        )
        repeated = sorted(name for name, count in names.items() if count > 1)
        if repeated:
            raise ValueError(
                f"fixtures, zones, equipment or sensors share an identifier: {', '.join(repeated)}"
            )
        return self

    @model_validator(mode="after")
    def _walkways_stay_clear(self) -> Self:
        in_the_way = [
            fixture
            for fixture in self.fixtures() + self.equipment_fixtures()
            if Obstruction.MOVEMENT in fixture.obstructs
            and fixture.bounds()[0].z < WALKWAY_HEADROOM_M
        ]
        for walkway_id, area in self.walkways():
            for fixture in in_the_way:
                if area.overlaps(fixture.corners()):
                    raise ValueError(f"{fixture.fixture_id} stands on the walkway {walkway_id}")
        return self

    def walkways(self) -> list[tuple[str, Strip]]:
        """Each walkway placed in the layout, and the floor it covers."""
        return [
            (primitive.fixture_id, primitive.area)
            for primitive in self.placed
            if isinstance(primitive, WalkwayPrimitive)
        ]

    def kept_clear(self) -> list[Strip]:
        """The areas of the floor kept clear of planting: walkways, service
        zones and keep-out volumes."""
        return [area for _, area in self.walkways()] + [zone.area for zone in self.zones]

    def fixtures(self) -> list[Fixture]:
        """Every fixture the layout describes, in the greenhouse's frame: what
        carries its rows, then what is placed one by one."""
        rows = [] if self.crop_rows is None else self.crop_rows.fixtures(self.kept_clear())
        return rows + [fixture for primitive in self.placed for fixture in primitive.fixtures()]

    def equipment_fixtures(self) -> list[Fixture]:
        """Its equipment, each piece as a fixture of its shape (`fixture`)."""
        return [piece.fixture() for piece in self.equipment]

    def sensor_fixtures(self) -> list[Fixture]:
        """Its sensors and cameras, each as a fixture of its housing."""
        return [sensor.fixture() for sensor in self.sensors]

    def obstructing(self, obstruction: Obstruction) -> list[Fixture]:
        """The fixtures, and the equipment, that stand in the way of
        `obstruction`, in the greenhouse's frame: the obstacles robots
        (movement), airflow or radiation (light) take from the layout
        (decision 0019)."""
        return [
            fixture
            for fixture in self.fixtures() + self.equipment_fixtures()
            if obstruction in fixture.obstructs
        ]

    def planting_positions(self) -> list[PlantingPosition]:
        """Every planting position outside the areas kept clear, row by row, in
        the greenhouse's frame."""
        if self.crop_rows is None:
            return []
        return self.crop_rows.planting_positions(self.kept_clear())


def outside_the_greenhouse(layout: Layout, envelope: Envelope) -> list[str]:
    """What of the layout does not fit inside the envelope: a fixture whose
    box reaches outside the space it encloses, or a planting position outside
    it."""
    fixtures = [
        fixture.fixture_id
        for fixture in layout.fixtures() + layout.equipment_fixtures() + layout.sensor_fixtures()
        if not encloses_hull(envelope, [(c.x, c.y, c.z) for c in fixture.corners()])
    ]
    positions = [
        position.position_id
        for position in layout.planting_positions()
        if not encloses(envelope, (position.point.x, position.point.y, position.point.z))
    ]
    zones = [
        zone.zone_id
        for zone in layout.zones
        if not encloses_hull(envelope, [(c.x, c.y, c.z) for c in zone_corners(zone)])
    ]
    return fixtures + positions + zones


def zone_corners(zone: Zone) -> list[Vector3]:
    """The corners of the volume a zone keeps, in the greenhouse's frame."""
    return [
        Vector3(x=corner.x, y=corner.y, z=z)
        for corner in zone.area.corners()
        for z in (0.0, zone.height)
    ]
