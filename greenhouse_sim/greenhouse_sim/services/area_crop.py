"""A run's crop grown by area through its days, as a viewer charts it
(decision 0083): a crop grown by area has no plants, and is charted, not
drawn.

Its course is its model's own quantities (`AreaAdapter.charted`), each in
its model's units, never converted to another model's (decision 0062): on
each of the run's days ended by a moment, each scope's state at the day's
start, once it has lived the days before, and the house's, the scopes'
mean weighted by their areas on the model's basis. Its values are the
model's predictions.

A run is asked for as its crop is (`greenhouse_sim.services.crop`), and
refused as it is, as is a moment outside it.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from greenhouse_sim.core.clock import days_ended
from greenhouse_sim.domain.scopes import AreaBasis
from greenhouse_sim.services.crop import of_plants, scenario_crop
from greenhouse_sim.services.crop_models import AreaQuantity, registration
from greenhouse_sim.services.errors import NotFound
from greenhouse_sim.services.runs import RunRequest, checked_moment
from greenhouse_sim.services.scenarios import scenario

if TYPE_CHECKING:
    # Typed only: the simulator imports the services that take it.
    from greenhouse_sim.services.simulator import Simulator


class ScopeCourse(BaseModel):
    """One scope of a crop grown by area through a run's days: its
    identifier, its area on its model's basis, in m², and its values, by
    quantity's key, one for each day, at the day's start."""

    model_config = ConfigDict(frozen=True)

    scope_id: str
    area_m2: float
    values: dict[str, list[float]]


class AreaCropCourse(BaseModel):
    """A run's crop grown by area `time_s` into it, through the days ended
    by then: its model, by its registry's name and in words
    (`model_name`), the basis its quantities are per m² of, the quantities
    charted, in order, the days, from 0, and, for each day, each scope's
    values (`scopes`, in the rows' order) and the house's (`house`), by
    quantity's key."""

    model_config = ConfigDict(frozen=True)

    time_s: float
    model: str
    model_name: str
    basis: AreaBasis
    quantities: list[AreaQuantity]
    days: list[int]
    scopes: list[ScopeCourse]
    house: dict[str, list[float]]


def area_crop_course(simulator: Simulator, run: RunRequest, time_s: float = 0.0) -> AreaCropCourse:
    """A run's crop grown by area `time_s` into it, day by day from its first
    to the last ended by then, as its model reads its states. Asked for as
    its crop is (`crop_scene`), and refused as it is; a crop grown plant by
    plant has no course by area, and is not found."""
    config = scenario(simulator.catalogue, run.scenario_id)
    checked_moment(config, time_s)
    grown_by = registration(config)
    area = grown_by.area
    if area is None:
        raise _grown_by_plant(run.scenario_id, grown_by.name)
    crop = scenario_crop(simulator, run)
    if of_plants(crop):
        raise _grown_by_plant(run.scenario_id, grown_by.name)
    basis = crop.rung.basis
    days = list(range(days_ended(time_s) + 1))
    # The crop keeps the start of every day it has lived (`keeps_days`): a
    # day not lived yet lives on from the one before, asked first.
    read = [
        {
            instance.scope_id: area.read(instance.state, config)
            for instance in crop.instances_on(day)
        }
        for day in days
    ]
    keys = [quantity.key for quantity in area.charted]
    scopes = [
        ScopeCourse(
            scope_id=scope.scope_id,
            area_m2=scope.area_m2(basis),
            values={key: [on_a_day[scope.scope_id][key] for on_a_day in read] for key in keys},
        )
        for scope in crop.scopes
    ]
    return AreaCropCourse(
        time_s=time_s,
        model=grown_by.name,
        model_name=grown_by.title,
        basis=basis,
        quantities=list(area.charted),
        days=days,
        scopes=scopes,
        house={key: house_course(scopes, key) for key in keys},
    )


def _grown_by_plant(scenario_id: str, model: str) -> NotFound:
    return NotFound(
        f"{scenario_id} grows its crop plant by plant, with the {model} model, not by area"
    )


def house_course(scopes: Sequence[ScopeCourse], key: str) -> list[float]:
    """A quantity of the whole house on each day: its scopes' values, each
    weighted by its area on the basis."""
    whole = sum(scope.area_m2 for scope in scopes)
    return [
        sum(value * scope.area_m2 for value, scope in zip(day, scopes, strict=True)) / whole
        for day in zip(*(scope.values[key] for scope in scopes), strict=True)
    ]
