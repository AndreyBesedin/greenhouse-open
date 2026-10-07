from datetime import date

from greenhouse_sim.airflow.prescribed import UniformAirflow
from greenhouse_sim.cfd.setup import CfdSetup
from greenhouse_sim.domain.envelope import OpeningKind
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.layout_files import load_layout
from greenhouse_sim.world.envelope import Envelope, Opening
from greenhouse_sim.world.geometry import Point2, Vector3

# The airflow QA case (P04): a single-span house with a wide door open at
# each end, face to face, and one block on the floor between them. Air is
# blown in through the front door and leaves through the back one, so it
# runs the length of the house and must go around and over the block, which
# leaves a wake behind it. Its second layout (`open`) is the same house
# without the block. Its one plant stands in a back corner, out of the way.
_DOOR_WIDTH_M = 2.0
_DOOR_HEIGHT_M = 2.2


def _door(opening_id: str, surface_id: str) -> Opening:
    # Centred across the house's 6.4 m width, standing on the floor.
    return Opening(
        opening_id=opening_id,
        kind=OpeningKind.DOOR,
        surface_id=surface_id,
        centre=Point2(x=3.2, y=_DOOR_HEIGHT_M / 2),
        width=_DOOR_WIDTH_M,
        height=_DOOR_HEIGHT_M,
        opening=1.0,
    )


AIRFLOW_BOX = ScenarioConfig(
    greenhouse_id="airflow_box",
    name="Airflow QA Box",
    description=(
        "Airflow QA case: air blown through a house from door to door, around one block "
        "between them, solved with OpenFOAM and compared with a prescribed breeze."
    ),
    variety="cherry_tomato",
    rows=1,
    columns=1,
    start_date=date(2026, 1, 1),
    duration_days=10,
    random_seed=404,
    envelope=Envelope(
        length=12.0,
        width=6.4,
        eave_height=3.0,
        ridge_height=3.65,
        openings=[_door("door_front", "end_wall_front"), _door("door_back", "end_wall_back")],
    ),
    # Its layout (scenarios/layouts/airflow_box/default.json): the block, 1 m
    # along the house, 2 m across and 1.5 m high, halfway between the doors.
    layout=load_layout("airflow_box"),
    # The breeze it is compared with: the CFD inlet's speed, along the house.
    airflow=UniformAirflow(velocity_m_s=Vector3(x=0.5, y=0.0, z=0.0)),
    cfd=CfdSetup(inlets=["door_front"]),
)
