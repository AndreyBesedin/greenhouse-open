"""A kind of equipment is a module and its registration (P14.5, decisions
0054 and 0055): a kind the simulator was not written with, registered from
another module, is placed by a layout, does what its capabilities say in a
run, and is drawn and named by what it does, with no change to the
climate, the scene or the viewer."""

from collections.abc import Iterator
from typing import Any, Final, Literal

import pytest
from pydantic import PositiveFloat, TypeAdapter, ValidationError

from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.catalogue import PACKAGED, Catalogue
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scene.snapshot import EQUIPMENT_COLORS, EQUIPMENT_OFF_COLOR, SceneEntityKind
from greenhouse_sim.services.climate_runs import climate_run
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.scenarios import SceneChanges, initial_scene
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.world.capabilities import Capability, Heats
from greenhouse_sim.world.equipment import (
    EQUIPMENT_KINDS,
    Equipment,
    Fan,
    Unit,
    register_equipment,
)

SCENARIO: Final = "climate_box"
HOUR_S: Final = 3600.0


class RadiantPanel(Unit):
    """A radiant panel standing on the floor: its power, all of it heating
    the air around its body."""

    kind: Literal["radiant_panel"] = "radiant_panel"
    power_w: PositiveFloat

    def rated(self) -> dict[str, float]:
        return {"power_w": self.power_w}

    def capabilities(self) -> tuple[Capability, ...]:
        return (Heats(power_w=self.power_w),)


# One in the climate box, clear of its other equipment.
PANEL: Final = {
    "actuator_id": "panel",
    "kind": "radiant_panel",
    "base": {"x": 3.0, "y": 1.0, "z": 0.0},
    "size_x": 0.2,
    "size_y": 1.0,
    "size_z": 0.8,
    "power_w": 5_000.0,
}


class LoudFan(Fan):
    """A fan of another class under the packaged fan's kind, which it does
    not register."""


# The climate box's fan, as a layout holds it.
(FAN,) = [piece for piece in SCENARIO_REGISTRY[SCENARIO].layout.equipment if isinstance(piece, Fan)]
# A piece of equipment of any kind registered, read as a layout reads it.
EQUIPMENT: Final = TypeAdapter[Any](Equipment)


@pytest.fixture
def registered() -> Iterator[type[RadiantPanel]]:
    """The panel's kind registered while a test runs, as another package
    would register its own, and forgotten after it."""
    register_equipment(RadiantPanel)
    yield RadiantPanel
    del EQUIPMENT_KINDS["radiant_panel"]


def _with_the_panel() -> dict[str, Any]:
    written = SCENARIO_REGISTRY[SCENARIO].model_dump(mode="json")
    written["layout"]["equipment"].append(PANEL)
    return written


def test_a_registered_kind_is_placed_by_a_layout_and_heats_the_house(
    registered: type[RadiantPanel],
) -> None:
    config = ScenarioConfig.model_validate(_with_the_panel())
    (panel,) = [piece for piece in config.layout.equipment if piece.actuator_id == "panel"]
    assert isinstance(panel, registered)
    # It is written as its kind writes it, and read back the same.
    assert ScenarioConfig.model_validate_json(config.model_dump_json()) == config

    with Simulator(Catalogue(PACKAGED.with_config(config))) as simulator:
        _, off = climate_run(simulator, RunRequest(SCENARIO))
        _, on = climate_run(simulator, RunRequest(SCENARIO, levels={"panel": 1.0}))
        scene = initial_scene(simulator.catalogue, SCENARIO)
        running = initial_scene(simulator.catalogue, SCENARIO, SceneChanges(levels={"panel": 1.0}))

    assert on.house.air_at(HOUR_S).temperature_c > off.house.air_at(HOUR_S).temperature_c + 1.0
    # Drawn as any piece of equipment, by what it does.
    (drawn,) = [e for e in scene.entities if e.entity_id == f"{SCENARIO}_panel"]
    assert drawn.kind == SceneEntityKind.EQUIPMENT
    assert drawn.properties == {
        "actuator_id": "panel",
        "level": 0.0,
        "device_kind": "radiant_panel",
        "does": "heats",
        "heats_w": 5_000.0,
        "power_w": 5_000.0,
    }
    # Grey while off, and in the colour of heating while it runs.
    (lit,) = [e for e in running.entities if e.entity_id == f"{SCENARIO}_panel"]
    assert (drawn.color, lit.color) == (EQUIPMENT_OFF_COLOR, EQUIPMENT_COLORS["heats"])


def test_a_kind_not_registered_is_refused_naming_those_that_are() -> None:
    with pytest.raises(ValidationError, match="no kind of equipment 'radiant_panel': the kinds"):
        ScenarioConfig.model_validate(_with_the_panel())


def test_a_piece_its_kind_refuses_is_refused_with_its_kinds_reason(
    registered: type[RadiantPanel],
) -> None:
    written = _with_the_panel()
    written["layout"]["equipment"][-1] = PANEL | {"power_w": -1.0}

    with pytest.raises(ValidationError, match="power_w: Input should be greater than 0"):
        ScenarioConfig.model_validate(written)


def test_a_kind_is_registered_by_its_own_name_once(registered: type[RadiantPanel]) -> None:
    class Another(RadiantPanel):
        pass

    with pytest.raises(ValueError, match="the kind 'radiant_panel' is RadiantPanel's"):
        register_equipment(Another)
    assert register_equipment(registered) is registered


@pytest.mark.parametrize(
    ("piece", "said"),
    [
        (RadiantPanel.model_validate(PANEL), "no kind of equipment 'radiant_panel': the kinds"),
        (LoudFan.model_validate(FAN.model_dump()), "the kind 'fan' is Fan's, not LoudFan's"),
    ],
)
def test_a_piece_given_of_a_class_not_registered_is_refused(piece: Any, said: str) -> None:
    """A piece given as it is, not written out, is refused as one written
    out would be: its class not registered, it would be written, and then
    not read back, or read back as the class registered under its kind."""
    with pytest.raises(ValidationError, match=said):
        EQUIPMENT.validate_python(piece)


def test_a_piece_given_of_its_kinds_class_is_taken_as_it_is_and_reads_back(
    registered: type[RadiantPanel],
) -> None:
    for piece in (FAN, registered.model_validate(PANEL)):
        assert EQUIPMENT.validate_python(piece) is piece
        assert EQUIPMENT.validate_json(EQUIPMENT.dump_json(piece)) == piece
