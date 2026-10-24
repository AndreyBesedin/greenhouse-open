"""Scenarios as manifests (P09.1): every scenario is read from its file, in
a format whose version it states, its house held as an installation (format
4, decision 0050) and each part's model named in its models (format 5,
decision 0054), and a manifest the simulator cannot read exactly is refused
with the reason. The manifests name
`greenhouse_sim/scenarios/scenario.schema.json`, which
`tests/test_published_schemas.py` holds to the configuration's model.
"""

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.catalogue import PACKAGED
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
            match="this simulator reads format 5, and formats 1, 2, 3, 4 migrated to it",
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
    current = _manifest("reference_greenhouse")
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
            "weather": "seasonal",
            "air_field": "uniform",
            "crop": "organ",
            "crop_walk": "walk",
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
    assert set(models["properties"]) == {"weather", "air_field", "crop", "crop_walk"}
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
    assert not {"weather", "airflow", "max_trusses", "height_noise_cm"} & set(schema["properties"])


def test_each_parts_model_and_its_parameters_are_read_from_its_section() -> None:
    document = _models(
        _manifest("climate_box"),
        crop={"model": "simple", "parameters": {"max_trusses": 4}},
        crop_walk={"model": "walk", "parameters": {"height_noise_cm": 0.5}},
        air_field={"model": "vortex"},
    )

    config = scenario_from_manifest("climate_box", document)

    assert (config.max_trusses, config.height_noise_cm) == (4, 0.5)
    assert config.airflow.kind == "vortex"
    # A part left out runs its default model with its defaults: its own
    # weather left out, the climate box's runs are under a constant one.
    del document["models"]["weather"]
    assert scenario_from_manifest("climate_box", document).weather.kind == "constant"


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
    current = _manifest("climate_box")
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
    }
    assert {
        key: migrated["notes"][key] for key in migrated["notes"] if key.startswith("models")
    } == {
        "models.weather": "Cold.",
        "models.crop": "Four.",
        "models.air_field": "Up.",
    }
    config = scenario_from_manifest("climate_box", older)
    assert config == SCENARIO_REGISTRY["climate_box"].model_copy(
        update={
            "airflow": config.airflow,
            "max_trusses": 4,
            "height_noise_cm": 0.5,
        }
    )
    assert config.airflow.kind == "vortex"
    with pytest.raises(InvalidManifest, match="a format 4 manifest has no 'models'"):
        scenario_from_manifest("climate_box", older | {"models": {}})
