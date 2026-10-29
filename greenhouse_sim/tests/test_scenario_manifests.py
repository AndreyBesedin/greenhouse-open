"""Scenarios as manifests (P09.1): every scenario is read from its file, in
a format whose version it states, its house held as an installation (format
4, decision 0050), each part's model named in its models (format 5,
decision 0054), its house's air's among them (format 6) and its
controller's (format 7), and a manifest the simulator cannot read exactly
is refused with the reason. The manifests name
`greenhouse_sim/scenarios/scenario.schema.json`, which
`tests/test_published_schemas.py` holds to the configuration's model.
"""

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from greenhouse_sim.climate.control import Control, HeatingLoop
from greenhouse_sim.climate.settings import GridAir, WholeHouseAir
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.catalogue import PACKAGED
from greenhouse_sim.scenarios.crop_parameters import RETIRED, CropWalk, SimpleCrop
from greenhouse_sim.scenarios.layout_files import load_layout
from greenhouse_sim.scenarios.manifest_files import (
    FIRST_SCENARIO,
    MANIFESTS_DIR,
    SCHEMA_FROM_A_MANIFEST_FILE,
    SCHEMA_VERSION,
    InvalidManifest,
    _migrated,
    manifest_digest,
    manifest_ids,
    manifest_json_schema,
    scenario_from_manifest,
)
from greenhouse_sim.scenarios.registry import ModelRun
from greenhouse_sim.services.errors import InvalidRequest, NotFound
from greenhouse_sim.services.scenarios import RunManifest, run_manifest


def _manifest(scenario_id: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((MANIFESTS_DIR / f"{scenario_id}.json").read_text())
    return document


# The packaged manifests as format 3 wrote them, before format 4 held their
# houses as installations: kept as they were, so that their migration is
# held to what they were, not to what it made of them.
FORMAT_3 = Path(__file__).parent / "fixtures" / "format_3_manifests"


def _in_format_3(scenario_id: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((FORMAT_3 / f"{scenario_id}.json").read_text())
    return document


def _with_its_part_at_the_top(
    document: dict[str, Any], version: int, part: str, field: str
) -> dict[str, Any]:
    """A manifest as the format `version` wrote it: the parameters of its
    `part`'s model a field of the configuration's own, `field`, and a note
    on that part on it."""
    models = dict(document["models"])
    section = models.pop(part, None)
    notes = {
        (field if about == f"models.{part}" else about): note
        for about, note in document["notes"].items()
    }
    older = document | {"schema_version": version, "models": models, "notes": notes}
    return older | ({field: section["parameters"]} if section is not None else {})


def _in_format_6(scenario_id: str) -> dict[str, Any]:
    """A packaged manifest as format 6 wrote it: its controller a field of
    the configuration's own, `control`, and a note on it on it."""
    return _with_its_part_at_the_top(_manifest(scenario_id), 6, "controller", "control")


def _in_format_5(scenario_id: str) -> dict[str, Any]:
    """A packaged manifest as format 5 wrote it: its house's air's settings
    a field of the configuration's own, `climate`, and a note on them on
    it, as well as its controller."""
    return _with_its_part_at_the_top(_in_format_6(scenario_id), 5, "house_air", "climate")


def _installation(document: dict[str, Any], **changes: Any) -> dict[str, Any]:
    """A manifest whose installation has `changes`."""
    return document | {"installation": document["installation"] | changes}


def _models(document: dict[str, Any], **sections: Any) -> dict[str, Any]:
    """A manifest whose models have `sections`, by part."""
    return document | {"models": document.get("models", {}) | sections}


def test_the_schema_holds_the_house_as_an_installation_and_refuses_what_it_does_not_have() -> None:
    schema: Any = manifest_json_schema()

    assert schema["additionalProperties"] is False
    assert schema["properties"]["installation"] == {"$ref": "#/$defs/Installation"}
    installation = schema["$defs"]["Installation"]
    assert installation["properties"]["layout"]["type"] == "string"
    assert installation["additionalProperties"] is False
    # Every crop row of a scenario grows a crop, so its installation has one.
    assert "row_crops" in installation["required"]
    assert installation["properties"]["row_crops"]["minItems"] == 1
    assert not {"envelope", "layout", "rows", "columns", "variety"} & set(schema["properties"])
    assert schema["properties"]["schema_version"] == {"const": SCHEMA_VERSION}
    assert {"schema_version", "installation"} <= set(schema["required"])
    assert "Layout" not in schema["$defs"]


def test_every_scenario_has_a_manifest_and_the_first_is_listed_first() -> None:
    assert list(SCENARIO_REGISTRY) == manifest_ids()
    assert manifest_ids()[0] == FIRST_SCENARIO
    assert manifest_ids()[1:] == sorted(manifest_ids()[1:])


@pytest.mark.parametrize("scenario_id", manifest_ids())
def test_every_manifest_names_its_schema_its_format_and_its_layout(scenario_id: str) -> None:
    document = _manifest(scenario_id)

    assert document["$schema"] == SCHEMA_FROM_A_MANIFEST_FILE
    assert document["schema_version"] == SCHEMA_VERSION
    named = document["installation"]["layout"]
    assert SCENARIO_REGISTRY[scenario_id].layout == load_layout(scenario_id, named)


def test_a_manifest_in_a_format_it_does_not_read_is_refused() -> None:
    for version in (SCHEMA_VERSION + 1, 0, None, "2", True):
        document = _manifest("climate_box") | {"schema_version": version}
        with pytest.raises(
            InvalidManifest,
            match="this simulator reads format 7, and formats 1, 2, 3, 4, 5, 6 migrated to it",
        ):
            scenario_from_manifest("climate_box", document)


def test_a_format_1_manifest_is_read_as_format_2_its_identifiers_held_to_it() -> None:
    """Format 2 narrowed the identifiers an item may have (#254); a format 1
    manifest is otherwise the same, and is read as format 2, or refused for
    an identifier format 2 does not allow, by name."""
    older = _in_format_3("climate_box") | {"schema_version": 1}
    assert scenario_from_manifest("climate_box", older) == SCENARIO_REGISTRY["climate_box"]

    openings = older["envelope"]["openings"]
    renamed = [openings[0] | {"opening_id": "roof:vent"}, *openings[1:]]
    named_so = older | {"envelope": older["envelope"] | {"openings": renamed}}
    with pytest.raises(ValidationError, match="opening_id"):
        scenario_from_manifest("climate_box", named_so)


def _with_a_thermostat(document: dict[str, Any], version: int) -> dict[str, Any]:
    """A format 3 manifest written as format 1 or 2 wrote it: its control's
    heating loop as a thermostat, with its control's day and night, and its
    note on its control as one on its thermostat."""
    control = document["control"]
    thermostat = control["heating"] | {
        "day_from_s": control["day_from_s"],
        "night_from_s": control["night_from_s"],
    }

    def renamed(written: dict[str, Any], value: Any) -> dict[str, Any]:
        return {
            ("thermostat" if key == "control" else key): (value if key == "control" else each)
            for key, each in written.items()
        }

    notes = renamed(document["notes"], document["notes"]["control"])
    return renamed(document, thermostat) | {"schema_version": version, "notes": notes}


@pytest.mark.parametrize("version", [1, 2])
def test_an_older_manifest_has_its_thermostat_read_as_its_controls_heating_loop(
    version: int,
) -> None:
    """Format 3 writes a heater's thermostat as its control's heating loop
    (P11.1); a format 1 or 2 manifest with one is migrated to it, its note
    on the thermostat a note on the control."""
    current = _in_format_3("reference_greenhouse")
    older = _with_a_thermostat(current, version)

    assert "control" not in older
    assert older["notes"]["thermostat"] == current["notes"]["control"]
    assert (
        scenario_from_manifest("reference_greenhouse", older)
        == SCENARIO_REGISTRY["reference_greenhouse"]
    )


def test_a_thermostat_is_refused_from_format_3_on_and_a_control_before_it() -> None:
    current = _in_format_6("reference_greenhouse")
    thermostat = _with_a_thermostat(current, 2)["thermostat"]
    with pytest.raises(InvalidManifest, match="fields it does not have: thermostat"):
        scenario_from_manifest("reference_greenhouse", current | {"thermostat": thermostat})
    with pytest.raises(InvalidManifest, match="a format 2 manifest has no 'control'"):
        scenario_from_manifest("reference_greenhouse", current | {"schema_version": 2})


@pytest.mark.parametrize("scenario_id", manifest_ids())
def test_a_format_3_manifest_holds_its_house_as_an_installation(scenario_id: str) -> None:
    """Format 4 holds a scenario's house as an installation (P12.1); a
    format 3 manifest is read as one, each row growing its crop, to the same
    scenario: its run is the same run. The packaged manifests are what the
    migration makes of theirs, their notes on the house on its parts."""
    older = _in_format_3(scenario_id)

    assert older["schema_version"] == 3
    assert scenario_from_manifest(scenario_id, older) == SCENARIO_REGISTRY[scenario_id]
    assert _migrated(scenario_id, older, 3) == _manifest(scenario_id)


def test_a_format_3_note_on_the_house_is_a_note_on_its_installation() -> None:
    older = _in_format_3("reference_greenhouse")
    notes = older["notes"]
    migrated: Any = _migrated(
        "reference_greenhouse", older | {"notes": notes | {"rows": "Four."}}, 3
    )

    assert migrated["notes"]["installation.envelope"] == notes["envelope"]
    assert migrated["notes"]["installation.row_crops"] == notes["crop_model"]
    assert migrated["notes"]["installation.layout"] == f"{notes['layout']} Four."
    assert not {"envelope", "layout", "crop_model", "rows"} & set(migrated["notes"])


def test_a_format_3_manifest_names_its_crop_and_is_called_by_its_name_or_identifier() -> None:
    older = _in_format_3("climate_box")

    unnamed = scenario_from_manifest("climate_box", older | {"name": ""})
    assert unnamed.name == ""
    renamed: Any = _migrated("climate_box", older | {"name": ""}, 3)
    assert renamed["installation"]["name"] == "climate_box"
    with pytest.raises(InvalidManifest, match="a crop's variety is named, not ''"):
        scenario_from_manifest("climate_box", older | {"variety": ""})
    with pytest.raises(InvalidManifest, match="a crop model is one of simple, organ, not 'tree'"):
        scenario_from_manifest("climate_box", older | {"crop_model": "tree"})
    with pytest.raises(InvalidManifest, match=r"a crop model is one of .*, not \['organ'\]"):
        scenario_from_manifest("climate_box", older | {"crop_model": ["organ"]})


def test_a_format_3_manifest_is_refused_where_its_plants_are_not_its_rows() -> None:
    older = _in_format_3("climate_box")

    with pytest.raises(InvalidManifest, match="its 1 rows of 32 plants are not its layout's crop"):
        scenario_from_manifest("climate_box", older | {"rows": 1, "columns": 32})
    with pytest.raises(InvalidManifest, match="a format 3 manifest has no 'installation'"):
        scenario_from_manifest("climate_box", older | {"installation": {}})


def test_a_manifest_writes_its_house_in_its_installation_only() -> None:
    document = _manifest("climate_box")

    with pytest.raises(InvalidManifest, match=r"not written beside it: \['rows'\]"):
        scenario_from_manifest("climate_box", document | {"rows": 2})
    with pytest.raises(InvalidManifest, match="holds its installation, written out, not None"):
        scenario_from_manifest(
            "climate_box", {key: value for key, value in document.items() if key != "installation"}
        )
    with pytest.raises(InvalidManifest, match="written out, not 'climate_box'"):
        scenario_from_manifest("climate_box", document | {"installation": "climate_box"})


def test_an_installation_a_run_cannot_grow_is_refused_saying_why() -> None:
    document = _manifest("climate_box")
    first, second = document["installation"]["row_crops"]

    with pytest.raises(InvalidManifest, match=r"cannot grow its installation: rows \[2\] have no"):
        scenario_from_manifest("climate_box", _installation(document, row_crops=[first]))
    with pytest.raises(InvalidManifest, match=r"grow different crops \(simple beefsteak, simple"):
        scenario_from_manifest(
            "climate_box",
            _installation(document, row_crops=[first, second | {"variety": "beefsteak"}]),
        )


def test_a_manifest_of_another_scenario_is_refused() -> None:
    with pytest.raises(InvalidManifest, match="describes 'climate_box'"):
        scenario_from_manifest("solar_lab", _manifest("climate_box"))


@pytest.mark.parametrize(
    ("change", "unknown"),
    [
        (lambda d: d | {"random_sed": 3}, "random_sed"),
        (
            lambda d: _installation(d, envelope=d["installation"]["envelope"] | {"lenght": 12.0}),
            "installation.envelope.lenght",
        ),
        (
            lambda d: _installation(
                d,
                envelope=d["installation"]["envelope"]
                | {
                    "openings": [
                        d["installation"]["envelope"]["openings"][0]
                        | {"centre": {"x": 0, "y": 1, "z": 2}}
                    ]
                },
            ),
            r"installation.envelope.openings\[0\].centre.z",
        ),
    ],
)
def test_a_field_the_configuration_does_not_have_is_refused(change: Any, unknown: str) -> None:
    """At any depth, including where the models themselves would ignore it."""
    with pytest.raises(InvalidManifest, match=f"fields it does not have: {unknown}"):
        scenario_from_manifest("climate_box", change(_manifest("climate_box")))


def test_a_field_a_model_forbids_is_refused_by_the_model() -> None:
    document = _manifest("climate_box")
    weather = document["models"]["weather"]
    parameters = weather["parameters"] | {"wind_from": 90.0}

    with pytest.raises(InvalidManifest, match=r"(?s)models\.weather: .*wind_from"):
        scenario_from_manifest(
            "climate_box", _models(document, weather=weather | {"parameters": parameters})
        )
    with pytest.raises(ValidationError, match="owner"):
        scenario_from_manifest("climate_box", _installation(document, owner="me"))


def test_notes_are_only_on_what_the_scenario_has() -> None:
    document = _manifest("climate_box")

    notes = document["notes"] | {"heaters": "two"}
    with pytest.raises(InvalidManifest, match="notes on what it does not have"):
        scenario_from_manifest("climate_box", document | {"notes": notes})
    # The house is noted by the part of its installation a note is about,
    # not by the fields format 3 wrote it in.
    for about in ("rows", "envelope", "installation.lenght"):
        with pytest.raises(
            InvalidManifest, match=f"notes on what it does not have: \\['{about}'\\]"
        ):
            scenario_from_manifest("climate_box", document | {"notes": {about: "A note."}})
    for about in ("installation", "installation.envelope", "installation.row_crops"):
        assert scenario_from_manifest("climate_box", document | {"notes": {about: "A note."}})
    with pytest.raises(InvalidManifest, match="notes are written by what each is about"):
        scenario_from_manifest("climate_box", document | {"notes": ["a note"]})


def test_a_manifest_names_a_layout_of_its_own_scenario() -> None:
    document = _manifest("tomato_compartment")

    assert scenario_from_manifest(
        "tomato_compartment", _installation(document, layout="propagation")
    )
    with pytest.raises(InvalidManifest, match="a layout is named"):
        scenario_from_manifest(
            "tomato_compartment", _installation(document, layout="../climate_box")
        )
    with pytest.raises(KeyError, match="no layout"):
        scenario_from_manifest("tomato_compartment", _installation(document, layout="hydroponic"))


def test_a_run_says_what_it_is_made_from() -> None:
    assert run_manifest(PACKAGED, "reference_greenhouse") == RunManifest(
        scenario_id="reference_greenhouse",
        schema_version=SCHEMA_VERSION,
        version=manifest_digest("reference_greenhouse"),
        random_seed=42,
        start_date=date(2026, 3, 1),
        duration_days=120,
        opening_day=86,
        crop_model="organ",
        variety="cherry_tomato",
        airflow="uniform",
        weather="default",
        weather_kind="seasonal",
        cloud_cover_pct=None,
        wind_from_deg=None,
        models={
            part: ModelRun(model=name, version=1)
            for part, name in {
                "weather": "seasonal",
                "air_field": "uniform",
                "crop": "organ",
                "crop_walk": "walk",
                "sunlight": "haurwitz_erbs",
                "sensors": "sampled",
                "house_air": "grid",
                "controller": "loops",
            }.items()
        },
    )


def test_a_run_under_another_weather_names_it_and_its_overrides() -> None:
    manifest = run_manifest(PACKAGED, "climate_box", "cold_spring_day@80~90")

    assert (manifest.weather, manifest.weather_kind) == ("cold_spring_day", "synthetic")
    assert (manifest.cloud_cover_pct, manifest.wind_from_deg) == (80.0, 90.0)
    # Its own, constant weather, its own seed and crop model.
    own = run_manifest(PACKAGED, "climate_box")
    assert (own.weather, own.weather_kind, own.random_seed) == ("default", "constant", 1201)
    assert (own.crop_model, own.opening_day) == ("simple", None)
    assert run_manifest(PACKAGED, "tomato_compartment").airflow == "buoyancy"


def test_a_run_manifest_is_refused_as_its_run_is() -> None:
    with pytest.raises(NotFound, match="no scenario"):
        run_manifest(PACKAGED, "nowhere")
    with pytest.raises(NotFound, match="no weather"):
        run_manifest(PACKAGED, "climate_box", "monsoon")
    with pytest.raises(InvalidRequest, match="cloud cover"):
        run_manifest(PACKAGED, "climate_box", "default@120")


def test_the_schema_writes_each_parts_model_in_its_models_not_at_the_top() -> None:
    schema: Any = manifest_json_schema()

    models = schema["properties"]["models"]
    assert set(models["properties"]) == {
        "weather",
        "air_field",
        "crop",
        "crop_walk",
        "sunlight",
        "sensors",
        "house_air",
        "controller",
    }
    weathers = models["properties"]["weather"]["oneOf"]
    assert [section["properties"]["model"] for section in weathers] == [
        {"const": "constant"},
        {"const": "synthetic"},
        {"const": "seasonal"},
        {"const": "recorded"},
    ]
    # A model's parameters leave out the kind its section's model says.
    assert "kind" not in schema["$defs"]["SeasonalWeather"]["properties"]
    assert "max_trusses" in schema["$defs"]["SimpleCrop"]["properties"]
    # A section gives its parameters if its model has one with no default,
    # as the recorded weather's file: the reader refuses it without them.
    assert [section["required"] for section in weathers] == [
        ["model"],
        ["model", "parameters"],
        ["model", "parameters"],
        ["model", "parameters"],
    ]
    assert schema["$defs"]["RecordedWeather"]["required"] == ["file"]
    with pytest.raises(InvalidManifest, match=r"(?s)models\.weather: .*file"):
        scenario_from_manifest(
            "climate_box", _models(_manifest("climate_box"), weather={"model": "recorded"})
        )
    assert not {
        "weather",
        "airflow",
        "max_trusses",
        "height_noise_cm",
        "climate",
        "control",
    } & set(schema["properties"])


def test_each_parts_model_and_its_parameters_are_read_from_its_section() -> None:
    document = _models(
        _manifest("climate_box"),
        crop={"model": "simple", "parameters": {"max_trusses": 4}},
        crop_walk={"model": "walk", "parameters": {"height_noise_cm": 0.5}},
        air_field={"model": "vortex"},
    )

    config = scenario_from_manifest("climate_box", document)

    assert (config.crop, config.crop_walk) == (
        SimpleCrop(max_trusses=4),
        CropWalk(height_noise_cm=0.5),
    )
    assert config.airflow.kind == "vortex"
    # A part left out runs its default model with its defaults: its own
    # weather left out, the climate box's runs are under a constant one.
    del document["models"]["weather"]
    assert scenario_from_manifest("climate_box", document).weather.kind == "constant"


def test_a_part_with_one_model_and_no_parameters_is_named_or_left_out() -> None:
    """The sunlight's and the sensors' one model each takes no parameters."""
    document = _models(
        _manifest("climate_box"),
        sunlight={"model": "haurwitz_erbs"},
        sensors={"model": "sampled"},
    )

    assert scenario_from_manifest("climate_box", document) == SCENARIO_REGISTRY["climate_box"]
    with pytest.raises(InvalidManifest, match="the sunlight has no model 'perez'"):
        scenario_from_manifest(
            "climate_box", _models(_manifest("climate_box"), sunlight={"model": "perez"})
        )
    with pytest.raises(InvalidManifest, match=r"(?s)models\.sensors: .*Extra inputs"):
        scenario_from_manifest(
            "climate_box",
            _models(_manifest("climate_box"), sensors={"model": "sampled", "parameters": {"x": 1}}),
        )


@pytest.mark.parametrize(
    ("sections", "said"),
    [
        ({"sun": {"model": "clear"}}, "no part models.sun; the parts are weather, air_field"),
        ({"weather": {"model": "stormy"}}, "the weather has no model 'stormy'"),
        ({"weather": {"parameters": {}}}, "models.weather names its model"),
        ({"weather": {"model": "constant", "kind": "constant"}}, "names its model"),
        (
            {"weather": {"model": "constant", "parameters": {"kind": "synthetic"}}},
            "its kind is its model's name, 'constant'",
        ),
        (
            {
                "air_field": {
                    "model": "uniform",
                    "parameters": {"velocity_m_s": {"x": 1, "y": 0, "z": 0, "w": 2}},
                }
            },
            r"fields it does not have: models.air_field.parameters.velocity_m_s.w",
        ),
        (
            {"crop": {"model": "organ"}},
            "its models.crop is the organ crop, but its rows grow the simple crop",
        ),
    ],
)
def test_a_part_or_a_model_the_registry_does_not_have_is_refused(
    sections: dict[str, Any], said: str
) -> None:
    with pytest.raises(InvalidManifest, match=said):
        scenario_from_manifest("climate_box", _models(_manifest("climate_box"), **sections))


def test_a_models_parameters_written_at_the_top_are_refused() -> None:
    document = _manifest("climate_box")

    with pytest.raises(InvalidManifest, match=r"written in its models.*\['max_trusses'\]"):
        scenario_from_manifest("climate_box", document | {"max_trusses": 4})
    with pytest.raises(InvalidManifest, match=r"\['weather'\]"):
        scenario_from_manifest("climate_box", document | {"weather": {"kind": "constant"}})
    with pytest.raises(InvalidManifest, match="notes on what it does not have"):
        scenario_from_manifest("climate_box", document | {"notes": {"weather": "Cold."}})
    assert scenario_from_manifest("climate_box", document | {"notes": {"models.weather": "Cold."}})


def test_a_format_4_manifest_writes_its_choices_in_its_models_to_the_same_scenario() -> None:
    """Format 5 writes the weather, the air field, the simple crop's
    settings and the walk's noises in their parts' sections (P14.1); a
    format 4 manifest is read as one, to the same scenario, its notes on
    them on their parts."""
    current = _in_format_5("climate_box")
    weather = current["models"]["weather"]
    older = {key: value for key, value in current.items() if key != "models"} | {
        "schema_version": 4,
        "weather": {"kind": weather["model"], **weather["parameters"]},
        "airflow": {"kind": "vortex"},
        "max_trusses": 4,
        "height_noise_cm": 0.5,
        "notes": current["notes"] | {"weather": "Cold.", "max_trusses": "Four.", "airflow": "Up."},
    }
    del older["notes"]["models.weather"]
    del older["notes"]["models.air_field"]

    migrated: Any = _migrated("climate_box", older, 4)

    assert migrated["models"] == {
        "weather": weather,
        "air_field": {"model": "vortex"},
        "crop": {"model": "simple", "parameters": {"max_trusses": 4}},
        "crop_walk": {"model": "walk", "parameters": {"height_noise_cm": 0.5}},
        "house_air": _manifest("climate_box")["models"]["house_air"],
    }
    assert {
        key: migrated["notes"][key] for key in migrated["notes"] if key.startswith("models")
    } == {
        "models.weather": "Cold.",
        "models.crop": "Four.",
        "models.air_field": "Up.",
        "models.house_air": current["notes"]["climate"],
    }
    config = scenario_from_manifest("climate_box", older)
    assert config == SCENARIO_REGISTRY["climate_box"].model_copy(
        update={
            "airflow": config.airflow,
            "crop": SimpleCrop(max_trusses=4),
            "crop_walk": CropWalk(height_noise_cm=0.5),
        }
    )
    assert config.airflow.kind == "vortex"
    with pytest.raises(InvalidManifest, match="a format 4 manifest has no 'models'"):
        scenario_from_manifest("climate_box", older | {"models": {}})


def test_a_scenario_of_organ_rows_gives_its_crop_no_simple_crops_settings() -> None:
    """The organ crop has a section of its own (P14.3): a format 4
    manifest of organ rows leaves out the simple crop's settings it wrote
    at the top, by which the engine's day grew the simple crop in its place,
    and a section of the organ crop that gives them is refused."""
    current = _in_format_5("reference_greenhouse")
    weather = current["models"]["weather"]
    air = current["models"]["air_field"]
    older = {key: value for key, value in current.items() if key != "models"} | {
        "schema_version": 4,
        "weather": {"kind": weather["model"], **weather["parameters"]},
        "airflow": {"kind": air["model"], **air.get("parameters", {})},
        "water_capacity_ml": 1500.0,
        "notes": {
            ("weather" if key == "models.weather" else key): note
            for key, note in current["notes"].items()
        },
    }

    migrated: Any = _migrated("reference_greenhouse", older, 4)

    assert "crop" not in migrated["models"]
    assert (
        scenario_from_manifest("reference_greenhouse", older)
        == SCENARIO_REGISTRY["reference_greenhouse"]
    )
    with pytest.raises(InvalidManifest, match=r"(?s)models\.crop: .*water_capacity_ml.*Extra"):
        scenario_from_manifest(
            "reference_greenhouse",
            _models(current, crop={"model": "organ", "parameters": {"water_capacity_ml": 1500.0}}),
        )


# The simple crop's settings of the engine's day, as a manifest written
# before it was removed may give them (decision 0059).
ENGINES_DAY = {
    "air_temperature_bounds": [18.0, 32.0],
    "humidity_bounds": [45.0, 85.0],
    "soil_moisture_noise_pct": 3.0,
    "air_temperature_noise_c": 0.4,
}


def test_a_manifest_that_gives_the_settings_of_the_engines_day_is_read_without_them() -> None:
    """Given in its crop's section, or at the top by a format 4 manifest,
    they are dropped, to the same scenario as without them; a setting the
    simple crop never had is still refused."""
    document = _manifest("climate_box")
    expected = SCENARIO_REGISTRY["climate_box"].model_copy(
        update={"crop": SimpleCrop(max_trusses=4)}
    )
    current = _in_format_5("climate_box")
    weather = current["models"]["weather"]
    air = current["models"]["air_field"]
    older = {key: value for key, value in current.items() if key != "models"} | {
        "schema_version": 4,
        "weather": {"kind": weather["model"], **weather["parameters"]},
        "airflow": {"kind": air["model"], **air["parameters"]},
        "max_trusses": 4,
        "notes": {
            ("weather" if key == "models.weather" else key): note
            for key, note in current["notes"].items()
        },
    }

    assert set(ENGINES_DAY) == set(RETIRED)
    crop = {"model": "simple", "parameters": {"max_trusses": 4}}
    assert scenario_from_manifest("climate_box", _models(document, crop=crop)) == expected
    retired = {"model": "simple", "parameters": {"max_trusses": 4} | ENGINES_DAY}
    assert scenario_from_manifest("climate_box", _models(document, crop=retired)) == expected
    assert scenario_from_manifest("climate_box", older) == expected
    assert scenario_from_manifest("climate_box", older | ENGINES_DAY) == expected
    never = {"model": "simple", "parameters": ENGINES_DAY | {"never_a_setting": 1.0}}
    with pytest.raises(InvalidManifest, match=r"(?s)models\.crop: .*never_a_setting"):
        scenario_from_manifest("climate_box", _models(document, crop=never))


@pytest.mark.parametrize("scenario_id", manifest_ids())
def test_a_format_5_manifest_writes_its_houses_air_as_the_grids_parameters(
    scenario_id: str,
) -> None:
    """Format 6 writes the house's air's settings as the parameters of its
    model (P14.6): a format 5 manifest is read as one whose house's air is
    the grid, which every run of it worked its air out by, to the same
    scenario, its note on them on that part; one that names no settings
    runs the grid's defaults."""
    older = _in_format_5(scenario_id)

    migrated: Any = _migrated(scenario_id, older, 5)

    assert migrated == _manifest(scenario_id)
    config = scenario_from_manifest(scenario_id, older)
    assert config == SCENARIO_REGISTRY[scenario_id]
    assert config.climate.kind == "grid"
    with pytest.raises(
        InvalidManifest, match="a format 5 manifest names no model of the house_air"
    ):
        scenario_from_manifest(scenario_id, _models(older, house_air={"model": "grid"}))


def test_a_house_of_one_well_mixed_air_is_read_from_its_section() -> None:
    """The whole house's model takes the house's settings without the
    grid's mixing, which it does not have."""
    starts = {"start_temperature_c": 16.0, "start_humidity_pct": 85.0}
    whole = _models(
        _manifest("climate_box"), house_air={"model": "whole_house", "parameters": starts}
    )

    config = scenario_from_manifest("climate_box", whole)

    assert config.climate == WholeHouseAir(**starts)
    assert config.climate.run_settings() == SCENARIO_REGISTRY["climate_box"].climate.run_settings()
    assert isinstance(SCENARIO_REGISTRY["climate_box"].climate, GridAir)
    with pytest.raises(InvalidManifest, match=r"(?s)models\.house_air: .*mixing_m2_s.*Extra"):
        scenario_from_manifest(
            "climate_box",
            _models(
                whole,
                house_air={"model": "whole_house", "parameters": starts | {"mixing_m2_s": 0.1}},
            ),
        )


@pytest.mark.parametrize("scenario_id", manifest_ids())
def test_a_format_6_manifest_writes_its_control_as_its_controllers_loops(
    scenario_id: str,
) -> None:
    """Format 7 writes a controller as the parameters of the controller's
    model (P14.6): a format 6 manifest is read as one whose controller is
    its loops, which every controller of format 6 was, to the same
    scenario, its note on it on that part; one with no control names no
    controller, and runs none."""
    older = _in_format_6(scenario_id)

    migrated: Any = _migrated(scenario_id, older, 6)

    assert migrated == _manifest(scenario_id)
    config = scenario_from_manifest(scenario_id, older)
    assert config == SCENARIO_REGISTRY[scenario_id]
    assert ("controller" in migrated["models"]) == ("control" in older)
    with pytest.raises(
        InvalidManifest, match="a format 6 manifest names no model of the controller"
    ):
        scenario_from_manifest(scenario_id, _models(older, controller={"model": "none"}))


def test_a_controller_is_read_from_its_section_and_not_from_the_top() -> None:
    """A manifest names its controller's loops, with their parameters, or
    none, which gives its scenario no control; and writes no control of the
    configuration's own."""
    current = _manifest("reference_greenhouse")
    loops = current["models"]["controller"]

    assert scenario_from_manifest("reference_greenhouse", current).control == Control(
        heating=HeatingLoop(actuator_id="heater", day_c=18.0, night_c=16.0)
    )
    climate_box = _models(_manifest("climate_box"), controller={"model": "none"})
    assert scenario_from_manifest("climate_box", climate_box) == SCENARIO_REGISTRY["climate_box"]
    with pytest.raises(InvalidManifest, match=r"written in its models.*\['control'\]"):
        scenario_from_manifest("reference_greenhouse", current | {"control": loops["parameters"]})
    with pytest.raises(InvalidManifest, match=r"(?s)models\.controller: .*one loop at least"):
        scenario_from_manifest(
            "climate_box", _models(_manifest("climate_box"), controller={"model": "loops"})
        )
    with pytest.raises(InvalidManifest, match="notes on what it does not have"):
        scenario_from_manifest("reference_greenhouse", current | {"notes": {"control": "Warm."}})
