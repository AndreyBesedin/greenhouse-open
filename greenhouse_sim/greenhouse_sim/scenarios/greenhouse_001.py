from datetime import date

from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world.envelope import Envelope, Opening, OpeningKind
from greenhouse_sim.world.fixtures import BoxPrimitive, WalkwayPrimitive
from greenhouse_sim.world.geometry import Point2, Vector3
from greenhouse_sim.world.layout import Layout
from greenhouse_sim.world.rows import TOMATO_GUTTER, CropRows
from greenhouse_sim.world.zones import Strip, Zone, ZoneKind

GREENHOUSE_001 = ScenarioConfig(
    greenhouse_id="gh_001",
    name="Simulation Greenhouse 001",
    description="Primary demo greenhouse: 40 cherry tomato plants, 28 days",
    variety="cherry_tomato",
    rows=4,
    columns=10,
    start_date=date(2026, 1, 1),
    duration_days=28,
    random_seed=1001,
    # Room around its four rows of ten plants: two 4.8 m spans, two 4 m bays,
    # a roof vent near each ridge and a door on the front gable.
    envelope=Envelope(
        length=8.0,
        width=9.6,
        eave_height=3.5,
        ridge_height=4.5,
        spans=2,
        bays=2,
        openings=[
            *(
                Opening(
                    opening_id=f"roof_vent_{span}",
                    kind=OpeningKind.ROOF_VENT,
                    surface_id=f"roof_{span}_right",
                    centre=Point2(x=0.0, y=0.85),
                    width=3.0,
                    height=0.8,
                    opening=0.2,
                )
                for span in (1, 2)
            ),
            Opening(
                opening_id="door_1",
                kind=OpeningKind.DOOR,
                surface_id="end_wall_front",
                centre=Point2(x=1.5, y=1.05),
                width=1.2,
                height=2.1,
            ),
        ],
    ),
    # Four rows of ten along the length, 1.6 m apart, centred in the house,
    # each on a tomato gutter. An aisle runs across the front, past the door,
    # and another along the right side wall; the back is kept for service,
    # with an irrigation unit that robots keep out of.
    layout=Layout(
        crop_rows=CropRows(
            origin=Point2(x=1.75, y=2.4),
            rows=4,
            positions_per_row=10,
            plant_pitch=0.5,
            row_spacing=1.6,
            support=TOMATO_GUTTER,
        ),
        placed=[
            WalkwayPrimitive(
                fixture_id="front_aisle",
                start=Point2(x=0.7, y=0.2),
                end=Point2(x=0.7, y=9.4),
                width=1.2,
            ),
            WalkwayPrimitive(
                fixture_id="side_aisle_right",
                start=Point2(x=1.3, y=1.1),
                end=Point2(x=7.8, y=1.1),
                width=1.0,
            ),
            BoxPrimitive(
                fixture_id="irrigation_unit",
                base=Vector3(x=7.35, y=8.6, z=0.0),
                size_x=0.6,
                size_y=1.0,
                size_z=1.6,
            ),
        ],
        zones=[
            Zone(
                zone_id="service_zone_back",
                kind=ZoneKind.SERVICE,
                area=Strip(start=Point2(x=7.35, y=1.8), end=Point2(x=7.35, y=9.4), width=1.1),
                height=2.2,
            ),
            Zone(
                zone_id="keep_out_irrigation",
                kind=ZoneKind.KEEP_OUT,
                area=Strip(start=Point2(x=7.35, y=7.9), end=Point2(x=7.35, y=9.3), width=1.0),
                height=2.0,
            ),
        ],
    ),
)
