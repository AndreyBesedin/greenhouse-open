from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from greenhouse_protocol.enums import SourceType
from greenhouse_protocol.greenhouse import (
    Compartment,
    GreenhouseDescription,
    GreenhouseLayout,
    Plant,
)

FORBIDDEN_SIMULATION_FIELDS = {
    "status",
    "current_step",
    "total_steps",
    "scenario_definition",
    "random_seed",
}


def test_plant_constructs_with_required_fields() -> None:
    plant = Plant(plant_id="plant_017", variety="cherry_tomato", row=2, position_in_row=7)

    assert plant.plant_id == "plant_017"
    assert plant.variety == "cherry_tomato"
    assert plant.row == 2
    assert plant.position_in_row == 7


def test_plant_optional_spatial_fields_default_to_none() -> None:
    plant = Plant(plant_id="plant_001", variety="cherry_tomato", row=1, position_in_row=1)

    assert plant.x is None
    assert plant.y is None
    assert plant.zone is None
    assert plant.tray_id is None


def test_plant_accepts_optional_spatial_fields() -> None:
    plant = Plant(
        plant_id="plant_017",
        variety="cherry_tomato",
        row=2,
        position_in_row=7,
        x=6.0,
        y=2.0,
        zone="A1",
        tray_id="tray_04",
    )

    assert plant.x == 6.0
    assert plant.y == 2.0
    assert plant.zone == "A1"
    assert plant.tray_id == "tray_04"


def test_plant_requires_plant_id() -> None:
    with pytest.raises(ValidationError):
        Plant(variety="cherry_tomato", row=1, position_in_row=1)  # type: ignore[call-arg]


def _make_greenhouse(**overrides: object) -> GreenhouseDescription:
    defaults: dict[str, object] = dict(
        greenhouse_id="gh_001",
        name="Simulation Greenhouse 001",
        description="Primary demo greenhouse",
        source_type=SourceType.SIMULATION,
        layout=GreenhouseLayout(rows=4, columns=10),
        plants=[Plant(plant_id="plant_001", variety="cherry_tomato", row=1, position_in_row=1)],
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    defaults.update(overrides)
    return GreenhouseDescription(**defaults)


def test_greenhouse_constructs_with_required_fields() -> None:
    greenhouse = _make_greenhouse()

    assert greenhouse.greenhouse_id == "gh_001"
    assert greenhouse.source_type == SourceType.SIMULATION
    assert greenhouse.layout.rows == 4
    assert greenhouse.layout.columns == 10
    assert len(greenhouse.plants) == 1


def test_greenhouse_model_has_no_simulation_specific_fields() -> None:
    assert set(GreenhouseDescription.model_fields).isdisjoint(FORBIDDEN_SIMULATION_FIELDS)


def test_a_description_holds_only_what_a_producer_states() -> None:
    """Anything a consumer adds on top - an owner, a replay position - belongs
    to the consumer's own record, not to the shared description."""
    assert set(GreenhouseDescription.model_fields) == {
        "greenhouse_id",
        "name",
        "description",
        "source_type",
        "crop",
        "layout",
        "plants",
        "compartments",
        "created_at",
    }


def _plant(plant_id: str) -> Plant:
    return Plant(plant_id=plant_id, variety="dwarf_tomato", row=1, position_in_row=1)


def test_greenhouse_has_no_compartments_by_default() -> None:
    greenhouse = _make_greenhouse()

    assert greenhouse.compartments == []
    assert greenhouse.compartment("3.06") is None
    assert greenhouse.all_plants == greenhouse.plants


def test_compartments_are_looked_up_by_id_and_can_hold_their_own_plants() -> None:
    reference = Compartment(
        compartment_id="3.06", name="Reference", plants=[_plant("p_306_1"), _plant("p_306_2")]
    )
    trigger = Compartment(compartment_id="3.08", name="Trigger", description="team Trigger")
    greenhouse = _make_greenhouse(plants=[], compartments=[reference, trigger])

    assert greenhouse.compartment("3.06") is reference
    assert greenhouse.compartment("3.08") is trigger
    assert trigger.plants == []
    assert [p.plant_id for p in greenhouse.all_plants] == ["p_306_1", "p_306_2"]


def test_all_plants_lists_unassigned_plants_before_compartment_plants() -> None:
    greenhouse = _make_greenhouse(
        plants=[_plant("loose")],
        compartments=[
            Compartment(compartment_id="a", name="A", plants=[_plant("a1")]),
            Compartment(compartment_id="b", name="B", plants=[_plant("b1")]),
        ],
    )

    assert [p.plant_id for p in greenhouse.all_plants] == ["loose", "a1", "b1"]


def test_compartment_ids_must_be_unique_within_a_greenhouse() -> None:
    with pytest.raises(ValidationError, match="duplicate compartment ids.*3.06"):
        _make_greenhouse(
            compartments=[
                Compartment(compartment_id="3.06", name="one"),
                Compartment(compartment_id="3.06", name="two"),
            ]
        )


def test_plant_ids_must_be_unique_across_the_whole_greenhouse() -> None:
    with pytest.raises(ValidationError, match="duplicate plant ids.*plant_001"):
        _make_greenhouse(
            plants=[_plant("plant_001")],
            compartments=[
                Compartment(compartment_id="3.06", name="one", plants=[_plant("plant_001")])
            ],
        )
