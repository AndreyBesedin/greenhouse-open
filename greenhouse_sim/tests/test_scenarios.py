import pytest
from pydantic import ValidationError

from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.crop_parameters import CropWalk, SimpleCrop


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
        ("crop.water_capacity_ml", 0.0),
        ("crop.truss_interval_days", 0),
        ("crop.fruit_growth_days_to_target", 0),
        ("crop.max_trusses", -1),
    ],
)
def test_a_scenario_refuses_a_count_or_capacity_no_run_can_have(field: str, value: float) -> None:
    # Each would fail later, dividing by zero or drawing a seed, not here.
    config = SCENARIO_REGISTRY["climate_box"].model_dump()
    section, _, name = field.rpartition(".")
    given = config | ({section: config[section] | {name: value}} if section else {name: value})

    with pytest.raises(ValidationError, match=name):
        ScenarioConfig.model_validate(given)


def test_a_configuration_written_with_its_settings_at_its_top_reads_them_in_its_sections() -> None:
    """As a configuration written before P14.3 held them, and as a
    downstream application may have kept it: none is lost."""
    config = SCENARIO_REGISTRY["climate_box"]
    written = config.model_dump(mode="json", exclude={"crop", "crop_walk"}) | {
        "truss_interval_days": 3,
        "ripening_days_bounds": [4, 7],
        "height_noise_cm": 0.5,
    }

    read = ScenarioConfig.model_validate(written)

    assert read == config.model_copy(
        update={
            "crop": SimpleCrop(truss_interval_days=3, ripening_days_bounds=(4, 7)),
            "crop_walk": CropWalk(height_noise_cm=0.5),
        }
    )
    assert ScenarioConfig(**written) == read
    with pytest.raises(
        ValidationError,
        match="its crop holds truss_interval_days, ripening_days_bounds, not beside",
    ):
        ScenarioConfig.model_validate(written | {"crop": {"kind": "simple"}})


def test_a_configuration_of_the_organ_crop_written_so_leaves_the_simple_crops_settings() -> None:
    """They were those by which the engine's day grew the simple crop in its
    place; the walk's are its crop walk's."""
    config = SCENARIO_REGISTRY["reference_greenhouse"]
    written = config.model_dump(mode="json", exclude={"crop", "crop_walk"}) | {
        "water_capacity_ml": 1500.0,
        "ripe_mass_noise_pct": 4.0,
    }

    read = ScenarioConfig.model_validate(written)

    assert read == config.model_copy(update={"crop_walk": CropWalk(ripe_mass_noise_pct=4.0)})
    assert read.simple_crop == SimpleCrop()
