import pytest
from pydantic import ValidationError

from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.config import ScenarioConfig


def test_registry_contains_exactly_the_configured_greenhouses() -> None:
    """The first scenario first, then the others by identifier."""
    assert list(SCENARIO_REGISTRY) == [
        "reference_greenhouse",
        "airflow_box",
        "climate_box",
        "sensor_lab",
        "solar_lab",
        "tomato_compartment",
    ]


def test_the_tomato_compartment_is_the_full_house_reference() -> None:
    config = SCENARIO_REGISTRY["tomato_compartment"]

    assert config.greenhouse_id == "tomato_compartment"
    assert (config.rows, config.columns) == (8, 40)
    assert config.duration_days == 28


def test_the_climate_box_is_the_small_quick_house() -> None:
    config = SCENARIO_REGISTRY["climate_box"]

    assert config.greenhouse_id == "climate_box"
    assert config.rows * config.columns == 32
    assert config.duration_days <= 15


def test_scenario_configs_have_distinct_random_seeds() -> None:
    seeds = {config.random_seed for config in SCENARIO_REGISTRY.values()}

    assert len(seeds) == len(SCENARIO_REGISTRY)


def test_a_scenario_describes_the_world_and_no_policy() -> None:
    """Which policy runs, and its thresholds, are the caller's choice about
    a run, not part of the simulated world."""
    fields = set(SCENARIO_REGISTRY["tomato_compartment"].model_dump())

    assert "management_policy" not in fields
    assert not fields & {
        "watering_trigger_reservoir_pct",
        "watering_amount_ml",
        "lower_plant_height_threshold_cm",
        "lower_plant_amount_cm",
        "harvest_ripe_fruit_count_threshold",
        "agent_tool_call_budget",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("rows", 0),
        ("columns", -1),
        ("duration_days", -5),
        ("random_seed", -1),
        ("water_capacity_ml", 0.0),
        ("truss_interval_days", 0),
        ("fruit_growth_days_to_target", 0),
        ("max_trusses", -1),
    ],
)
def test_a_scenario_refuses_a_count_or_capacity_no_run_can_have(field: str, value: float) -> None:
    # Each would fail later, dividing by zero or drawing a seed, not here.
    config = SCENARIO_REGISTRY["climate_box"].model_dump()

    with pytest.raises(ValidationError, match=field):
        ScenarioConfig.model_validate(config | {field: value})
