"""The one action format (decision 0046): each kind, what it refuses, and
the parts an authorisation grant can limit."""

import pytest
from pydantic import TypeAdapter, ValidationError

from greenhouse_protocol.actions import (
    MAX_WATER_AMOUNT_ML,
    Action,
    ActionRef,
    ActionTargets,
    Harvest,
    HarvestScope,
    Inspect,
    Lower,
    RemoveLeaf,
    SetLevel,
    SetTarget,
    Water,
    targets_of,
)

ACTION = TypeAdapter[Action](Action)


@pytest.mark.parametrize(
    "document, kind",
    [
        ({"kind": "set_level", "device_id": "heater", "level": 0.5}, SetLevel),
        ({"kind": "set_level", "device_id": "heater", "level": "auto"}, SetLevel),
        ({"kind": "set_target", "target": "heating_day", "value_c": 22}, SetTarget),
        ({"kind": "water", "plant_id": "p30", "amount_ml": 500}, Water),
        ({"kind": "harvest", "plant_id": "p30", "scope": "ripe"}, Harvest),
        ({"kind": "harvest", "plant_id": "p30", "scope": "truss", "organ_id": "t3"}, Harvest),
        ({"kind": "lower", "plant_id": "p30", "by_internodes": 2}, Lower),
        ({"kind": "remove_leaf", "plant_id": "p30", "leaf_id": "l7"}, RemoveLeaf),
        ({"kind": "inspect", "plant_id": "p30", "reason": "a yellow leaf"}, Inspect),
    ],
)
def test_each_kind_is_read_by_its_kind(document: dict[str, object], kind: type) -> None:
    action = ACTION.validate_python(document)

    assert isinstance(action, kind)
    assert ACTION.validate_json(ACTION.dump_json(action)) == action


@pytest.mark.parametrize(
    "document",
    [
        {"kind": "set_level", "device_id": "heater", "level": 1.5},
        {"kind": "set_level", "device_id": "heater", "level": "manual"},
        {"kind": "set_level", "device_id": "", "level": 0.5},
        {"kind": "set_target", "target": "heating_day", "value_c": 41},
        {"kind": "set_target", "target": "venting_day", "value_c": 22},
        {"kind": "water", "plant_id": "p30", "amount_ml": 0},
        {"kind": "water", "plant_id": "p30", "amount_ml": MAX_WATER_AMOUNT_ML + 1},
        {"kind": "harvest", "plant_id": "p30", "scope": "ripe", "organ_id": "f1"},
        {"kind": "harvest", "plant_id": "p30", "scope": "fruit"},
        {"kind": "lower", "plant_id": "p30"},
        {"kind": "lower", "plant_id": "p30", "by_cm": 10, "by_internodes": 2},
        {"kind": "inspect", "plant_id": "p30", "reason": "   "},
        {"kind": "prune", "plant_id": "p30"},
        {"kind": "water", "plant_id": "p30", "amount_ml": 500, "at": "noon"},
        {"kind": "lower", "plant_id": "p30", "by_cm": float("inf")},
        {"kind": "set_level", "device_id": "heater", "level": float("nan")},
    ],
)
def test_what_an_action_cannot_say_is_refused(document: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ACTION.validate_python(document)


def test_an_action_cannot_be_edited() -> None:
    action = Water(plant_id="p30", amount_ml=500)

    with pytest.raises(ValidationError):
        action.amount_ml = 600  # type: ignore[misc]


def test_a_reference_names_an_action_an_occurrence_or_a_fallback() -> None:
    assert str(ActionRef(action_id="harvest")) == "harvest"
    assert str(ActionRef(action_id="harvest", occurrence=3)) == "harvest@3"
    assert str(ActionRef(action_id="vent", fallback=True)) == "vent/fallback"


@pytest.mark.parametrize("action_id", ["harvest@3", "vent/fallback", "", "a b"])
def test_an_action_id_is_the_protocols_own_grammar(action_id: str) -> None:
    with pytest.raises(ValidationError):
        ActionRef(action_id=action_id)


@pytest.mark.parametrize(
    "action, targets",
    [
        (SetLevel(device_id="heater", level=1.0), ActionTargets(devices=frozenset({"heater"}))),
        (
            SetTarget(target="heating_night", value_c=16),
            ActionTargets(targets=frozenset({"heating_night"})),
        ),
        (Water(plant_id="p30", amount_ml=5), ActionTargets(plants=frozenset({"p30"}))),
        (
            Harvest(plant_id="p30", scope=HarvestScope.RIPE),
            ActionTargets(plants=frozenset({"p30"})),
        ),
        (Lower(plant_id="p30", by_cm=10), ActionTargets(plants=frozenset({"p30"}))),
        (RemoveLeaf(plant_id="p30", leaf_id="l7"), ActionTargets(plants=frozenset({"p30"}))),
        (Inspect(plant_id="p30", reason="why"), ActionTargets(plants=frozenset({"p30"}))),
    ],
)
def test_what_each_action_acts_on(action: Action, targets: ActionTargets) -> None:
    assert targets_of(action) == targets
