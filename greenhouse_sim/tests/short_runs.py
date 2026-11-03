"""What a test of a run's logic runs, when what it holds is that the path runs
and not what the numbers come to: the climate box of one plant, whose sensors
read four times a day, cut to a few days.

A packaged scenario's day is slow for two reasons. Its sensors sample every
minute, and each moment sampled draws the air and the sun over every cell of the
house. Each of its 32 plants is worked out on its own, under its own light. Cut
so, a day is worked out in about half a second, through the same run, store and
worker as any other: a sensor's first sample still reads the air on the grid, the
later ones the whole house's, and the scenario is written to the store and read
back as an uploaded one is.

These are test scenarios, never packaged, and no digest is kept of them: a test
compares two runs of one, so their numbers do not matter, only that they differ
when a change should make them differ.
"""

from typing import Final

from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.crop_parameters import OrganCrop
from greenhouse_sim.units import HOUR_S

BOX: Final = "climate_box"
REFERENCE: Final = "reference_greenhouse"
# So far apart that only the run's first sample reads the air on the grid, whose
# first two hours cost as much as the rest of the day's house.
READS_EVERY_S: Final = 6 * HOUR_S


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
