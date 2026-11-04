"""What a test of logic runs on, in seconds where a packaged scenario's own run
takes minutes. Two kinds, by what the test keeps.

`cut` is a packaged scenario cut to a few days, for a test that keeps that scenario's
plants, devices and start. The time a run takes goes on the air cell by cell through
its first two hours, on the sun's shadows through each day, and on what its sensors
sample, a whole field for each sample (run under a profiler). So a cut scenario has
its air the whole house's and, unless it keeps its season, a calm, constant weather
under a polar night. It keeps its identifier. A test that holds what the air's grid,
the sun, a season or many plants do runs on the scenario itself, or says so.

`one_plant_box` and `tended_box` are the climate box of one plant, whose sensors read
four times a day, for a test that holds that a path runs and not what the numbers come
to. Each of a packaged scenario's 32 plants is worked out on its own, under its own
light, and its sensors sample every minute. Cut so, a day is worked out in about half a
second, through the same run, store and worker as any other: a sensor's first sample
still reads the air on the grid, the later ones the whole house's, and the scenario is
written to the store and read back as an uploaded one is. These are test scenarios,
never packaged, and no digest is kept of them: a test compares two runs of one, so
their numbers do not matter, only that they differ when a change should make them differ.
"""

from collections.abc import Iterable
from typing import Any, Final

from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.catalogue import PACKAGED, Catalogue
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.crop_parameters import OrganCrop
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.units import HOUR_S
from greenhouse_sim.weather.sources import ConstantWeather
from greenhouse_sim.world.site import DEFAULT_SITE

DAYS: Final = 4
# Far enough north that the sun stays under the horizon through the first
# five days of March, and all January: the reference run's and the box's starts.
POLAR_LATITUDE_DEG: Final = 85.0
BOX: Final = "climate_box"
REFERENCE: Final = "reference_greenhouse"
# So far apart that only the run's first sample reads the air on the grid, whose
# first two hours cost as much as the rest of the day's house.
READS_EVERY_S: Final = 6 * HOUR_S


def cut(
    scenario_id: str,
    *,
    days: int = DAYS,
    plants: tuple[int, int] | None = None,
    season: bool = False,
    sensors: Iterable[str] | None = None,
    **changes: Any,
) -> ScenarioConfig:
    """The packaged scenario `scenario_id`, its runs `days` long, its air the
    whole house's, `plants` rows and columns of plants if named, only the
    `sensors` named if any are; under its own site and weather if it keeps
    its `season`, and otherwise in the dark; and with `changes` to the rest
    of its configuration."""
    config = SCENARIO_REGISTRY[scenario_id]
    air = config.climate.model_dump(exclude={"kind", "mixing_m2_s"})
    cuts: dict[str, Any] = {
        "duration_days": days,
        "climate": {"kind": "whole_house", **air},
    }
    if plants is not None:
        cuts |= {"rows": plants[0], "columns": plants[1]}
    if not season:
        cuts |= {
            "site": DEFAULT_SITE.model_copy(update={"latitude_deg": POLAR_LATITUDE_DEG}),
            "weather": ConstantWeather(),
        }
    if sensors is not None:
        named = set(sensors)
        layout = config.layout.model_dump()
        layout["sensors"] = [s for s in layout["sensors"] if s["sensor_id"] in named]
        cuts["layout"] = layout
    return ScenarioConfig.model_validate(config.model_dump() | cuts | changes)


def simulator_of(*configs: ScenarioConfig, **given: Any) -> Simulator:
    """A simulator that knows `configs` in place of the packaged scenarios of
    their identifiers, and of any other identifier beside them, made with
    `given`."""
    packaged = PACKAGED
    for config in configs:
        if config.greenhouse_id in PACKAGED.ids():
            packaged = packaged.with_config(config)
    made = Simulator(Catalogue(packaged), **given)
    for config in configs:
        if config.greenhouse_id not in PACKAGED.ids():
            made.catalogue.register(config)
    return made


def one_plant_box(greenhouse_id: str, days: int) -> ScenarioConfig:
    """The climate box, of one plant, its sensors reading every six hours, for
    `days` days: no heating loop to set a target of, and the simple crop."""
    box = SCENARIO_REGISTRY[BOX]
    rows = box.layout.crop_rows
    assert rows is not None
    layout = box.layout.model_copy(
        update=dict(
            crop_rows=rows.model_copy(update=dict(rows=1, positions_per_row=1)),
            sensors=[
                sensor.model_copy(update=dict(cadence_s=READS_EVERY_S))
                for sensor in box.layout.sensors
            ],
        )
    )
    return box.model_copy(
        update=dict(
            greenhouse_id=greenhouse_id, duration_days=days, rows=1, columns=1, layout=layout
        )
    )


def tended_box(greenhouse_id: str, days: int) -> ScenarioConfig:
    """`one_plant_box` with the reference greenhouse's heating loop and organ crop,
    under its weather, on its site, from its first day: what a target can be set of
    and a crop action done to, warm enough for its crop to develop, at a fraction
    of a day of the reference house, whose 39 fixtures shade every minute's sun."""
    reference = SCENARIO_REGISTRY[REFERENCE]
    return one_plant_box(greenhouse_id, days).model_copy(
        update=dict(
            control=reference.control,
            crop_model=CropModel.ORGAN,
            crop=OrganCrop(),
            crop_work=reference.crop_work,
            weather=reference.weather,
            site=reference.site,
            start_date=reference.start_date,
        )
    )
