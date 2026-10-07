"""A scenario's environment fields: its greenhouse's air, as a client draws it.

A field covers the air under the greenhouse's gutters: its floor, from its
front right corner, up to its eaves. The air in the roof's spans above them
is left out until a solver needs it. Its cells are at most `CELL_M` wide.
"""

from collections.abc import Callable
from typing import Final

from greenhouse_sim.fields.field import EnvironmentField, FieldDocument, FieldGrid
from greenhouse_sim.fields.synthetic import shear_field
from greenhouse_sim.services.errors import NotFound
from greenhouse_sim.services.scenarios import scenario
from greenhouse_sim.world.geometry import Vector3

# The widest a field's cell may be, in metres.
CELL_M: Final = 0.5

# The fields a scenario offers, by name.
_FIELDS: Final[dict[str, Callable[[str, FieldGrid], EnvironmentField]]] = {
    "shear": shear_field,
}


def field_names(scenario_id: str) -> list[str]:
    """The fields a scenario offers."""
    scenario(scenario_id)
    return list(_FIELDS)


def grid(scenario_id: str) -> FieldGrid:
    """The grid a scenario's fields cover: its greenhouse's air under the
    gutters."""
    envelope = scenario(scenario_id).envelope
    return FieldGrid.over(
        Vector3(x=0.0, y=0.0, z=0.0),
        Vector3(x=envelope.length, y=envelope.width, z=envelope.eave_height),
        CELL_M,
    )


def field(scenario_id: str, name: str) -> FieldDocument:
    """One of a scenario's fields, as it is published."""
    make = _FIELDS.get(name)
    if make is None:
        known = ", ".join(_FIELDS)
        raise NotFound(f"scenario {scenario_id!r} has no field {name!r}; it has {known}")
    return make(f"{scenario_id}_{name}", grid(scenario_id)).document()
