from datetime import date

from greenhouse_sim.airflow.prescribed import UniformAirflow
from greenhouse_sim.climate.settings import ClimateSettings
from greenhouse_sim.domain.envelope import OpeningKind
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.layout_files import load_layout
from greenhouse_sim.weather.sources import ConstantWeather
from greenhouse_sim.world.envelope import Envelope, Opening
from greenhouse_sim.world.geometry import Point2, Vector3

# The small house (P05.0): small enough to follow its air closely, where
# P05's equipment is placed and its QA run. It has one opening of each kind,
# all shut, so that equipment acts on still, closed air.
CLIMATE_BOX = ScenarioConfig(
    greenhouse_id="climate_box",
    name="Climate box",
    description=(
        "A small single-span house of 32 tomato plants, shut and still, where climate "
        "equipment is tried, 14 days"
    ),
    variety="cherry_tomato",
    rows=2,
    columns=16,
    start_date=date(2026, 1, 1),
    duration_days=14,
    random_seed=1201,
    # One 6.4 m span, three 4 m bays, 4 m to the gutters.
    envelope=Envelope(
        length=12.0,
        width=6.4,
        eave_height=4.0,
        ridge_height=4.8,
        bays=3,
        openings=[
            Opening(
                opening_id="roof_vent",
                kind=OpeningKind.ROOF_VENT,
                surface_id="roof_1_right",
                centre=Point2(x=0.0, y=0.8),
                width=4.0,
                height=1.0,
                opening=0.0,
            ),
            Opening(
                opening_id="side_vent",
                kind=OpeningKind.SIDE_VENT,
                surface_id="side_wall_right",
                centre=Point2(x=0.0, y=0.5),
                width=3.0,
                height=0.6,
                opening=0.0,
            ),
            Opening(
                opening_id="door",
                kind=OpeningKind.DOOR,
                surface_id="end_wall_front",
                centre=Point2(x=5.0, y=1.05),
                width=1.2,
                height=2.1,
            ),
        ],
    ),
    # Its layout (scenarios/layouts/climate_box/default.json): two rows of 16
    # plants along the house, 1.6 m apart about its middle, on gutters under
    # crop wires, behind a path across the front; and its equipment, all off
    # until commanded: a fan high over the front path blowing down the house,
    # a 10 kW heater in the back right corner, and a dehumidifier against the
    # left side wall, halfway along; and its sensors: temperature and humidity
    # in each half of the house, an anemometer in the fan's jet, CO2 in the
    # middle and PAR under the roof.
    layout=load_layout("climate_box"),
    # Still air, so that a fan's jet stands out.
    airflow=UniformAirflow(velocity_m_s=Vector3(x=0.0, y=0.0, z=0.0)),
    # A cold, damp night, when heating and drying matter: 8 °C and 90%
    # outside, still, and 16 °C and 85% inside to start, through single glass.
    climate=ClimateSettings(start_temperature_c=16.0, start_humidity_pct=85.0),
    weather=ConstantWeather(air_temperature_c=8.0, relative_humidity_pct=90.0),
)
