"""Scenarios as manifests (P09.1): every scenario is read from its file, in
a format whose version it states, its house held as an installation (format
4, decision 0050), and a manifest the simulator cannot read exactly is
refused with the reason. The manifests name
`greenhouse_sim/scenarios/scenario.schema.json`, which
`tests/test_published_schemas.py` holds to the configuration's model.
"""

import json
from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.layout_files import load_layout
from greenhouse_sim.scenarios.manifest_files import (
    FIRST_SCENARIO,
    MANIFESTS_DIR,
    SCHEMA_FROM_A_MANIFEST_FILE,
    SCHEMA_VERSION,
    InvalidManifest,
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


def _in_format_3(scenario_id: str, document: dict[str, Any]) -> dict[str, Any]:
    """A format 4 manifest as format 3 wrote it: its installation's house as
    fields of its own, its rows and columns its layout's crop rows and their
    positions, and the crop every row grows."""
    installation = document["installation"]
    (crop,) = {(each["crop_model"], each["variety"]) for each in installation["row_crops"]}
    crop_rows = load_layout(scenario_id, installation["layout"]).crop_rows
    assert crop_rows is not None
    house = {
        "variety": crop[1],
        "rows": crop_rows.rows,
        "columns": crop_rows.positions_per_row,
        "crop_model": crop[0],
        "envelope": installation["envelope"],
        "layout": installation["layout"],
    }
    rest = {key: value for key, value in document.items() if key != "installation"}
    return rest | house | {"schema_version": 3}


def _installation(document: dict[str, Any], **changes: Any) -> dict[str, Any]:
    """A manifest whose installation has `changes`."""
    return document | {"installation": document["installation"] | changes}


def test_the_schema_holds_the_house_as_an_installation_and_refuses_what_it_does_not_have() -> None:
    schema: Any = manifest_json_schema()

    assert schema["additionalProperties"] is False
    assert schema["properties"]["installation"] == {"$ref": "#/$defs/Installation"}
    installation = schema["$defs"]["Installation"]
    assert installation["properties"]["layout"]["type"] == "string"
    assert installation["additionalProperties"] is False
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
            match="this simulator reads format 4, and formats 1, 2, 3 migrated to it",
        ):
            scenario_from_manifest("climate_box", document)


def test_a_format_1_manifest_is_read_as_format_2_its_identifiers_held_to_it() -> None:
    """Format 2 narrowed the identifiers an item may have (#254); a format 1
    manifest is otherwise the same, and is read as format 2, or refused for
    an identifier format 2 does not allow, by name."""
    older = _in_format_3("climate_box", _manifest("climate_box")) | {"schema_version": 1}
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
    current = _in_format_3("reference_greenhouse", _manifest("reference_greenhouse"))
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
    scenario: its run is the same run."""
    older = _in_format_3(scenario_id, _manifest(scenario_id))

    assert "installation" not in older
    assert scenario_from_manifest(scenario_id, older) == SCENARIO_REGISTRY[scenario_id]


def test_a_format_3_manifest_is_refused_where_its_plants_are_not_its_rows() -> None:
    older = _in_format_3("climate_box", _manifest("climate_box"))

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
    with pytest.raises(InvalidManifest, match="grow different crops .simple beefsteak, simple"):
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

    with pytest.raises(ValidationError, match="wind_from"):
        scenario_from_manifest(
            "climate_box", document | {"weather": document["weather"] | {"wind_from": 90.0}}
        )
    with pytest.raises(ValidationError, match="owner"):
        scenario_from_manifest("climate_box", _installation(document, owner="me"))


def test_notes_are_only_on_what_the_scenario_has() -> None:
    document = _manifest("climate_box")

    notes = document["notes"] | {"heaters": "two"}
    with pytest.raises(InvalidManifest, match="notes on what it does not have"):
        scenario_from_manifest("climate_box", document | {"notes": notes})
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
    assert run_manifest("reference_greenhouse") == RunManifest(
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
    )


def test_a_run_under_another_weather_names_it_and_its_overrides() -> None:
    manifest = run_manifest("climate_box", "cold_spring_day@80~90")

    assert (manifest.weather, manifest.weather_kind) == ("cold_spring_day", "synthetic")
    assert (manifest.cloud_cover_pct, manifest.wind_from_deg) == (80.0, 90.0)
    # Its own, constant weather, its own seed and crop model.
    own = run_manifest("climate_box")
    assert (own.weather, own.weather_kind, own.random_seed) == ("default", "constant", 1201)
    assert (own.crop_model, own.opening_day) == ("simple", None)
    assert run_manifest("tomato_compartment").airflow == "buoyancy"


def test_a_run_manifest_is_refused_as_its_run_is() -> None:
    with pytest.raises(NotFound, match="no scenario"):
        run_manifest("nowhere")
    with pytest.raises(NotFound, match="no weather"):
        run_manifest("climate_box", "monsoon")
    with pytest.raises(InvalidRequest, match="cloud cover"):
        run_manifest("climate_box", "default@120")
