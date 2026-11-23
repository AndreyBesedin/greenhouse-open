"""A house's components, described in its installation (P24.2, decision
0080): its cover's materials, each wall's boundary, its floor and layers,
its screens and pipe networks, named from the catalogue of materials or
given by their properties; read back the same, refused by field outside
their ranges, written nowhere while undescribed, and refused, by name, by a
house air model that cannot model them."""

import copy
import json
from typing import Any, Final

import pytest
from pydantic import ValidationError

from greenhouse_sim.builder.installation import assess_installation
from greenhouse_sim.builder.portable import (
    InstallationFileError,
    export_installation,
    import_installation,
)
from greenhouse_sim.domain.components import Component
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.installation import Installation, scenario_installation
from greenhouse_sim.scenarios.manifest_files import (
    MANIFESTS_DIR,
    manifest_ids,
    scenario_from_manifest,
)
from greenhouse_sim.services import builder
from greenhouse_sim.solar.glass import DIFFUSE_TRANSMITTANCE
from greenhouse_sim.world.components import HouseComponents, OnASpace
from greenhouse_sim.world.materials import (
    COVER_MATERIALS,
    LAYER_MATERIALS,
    SCREEN_CLOTHS,
    CoverMaterial,
    CoverMaterialName,
    LayerMaterial,
    LayerMaterialName,
    ScreenCloth,
    ScreenClothName,
    material,
)

# The house the components are described in: 12 m by 9.6 m, its eaves at
# 4 m, as its scenario has it, with a heater and roof vents.
SCENARIO: Final = "reference_greenhouse"
# A twin-wall sheet given by its properties, for a test: no source.
TWIN_WALL: Final = {
    "shortwave_beam_transmittance": 0.8,
    "shortwave_diffuse_transmittance": 0.7,
    "shortwave_reflectance": 0.12,
    "longwave_emissivity": 0.9,
    "longwave_transmittance": 0.03,
    "thickness_m": 0.008,
    "conductivity_w_m_k": 0.2,
    "volumetric_heat_capacity_j_m3_k": 1.4e6,
}
THERMAL_SCREEN: Final = {
    "screen_id": "energy_screen",
    "kind": "thermal",
    "material": "thermal_screen_cloth",
    "height_m": 4.0,
    "closure": 0.0,
}
RAIL_PIPES: Final = {
    "network_id": "rail_pipes",
    "kind": "rail",
    "length_m": 180.0,
    "outer_diameter_m": 0.051,
    "inner_diameter_m": 0.047,
    "height_m": 0.1,
    "longwave_emissivity": 0.88,
}
# Every component a house may describe, as its file writes them.
COMPONENTS: Final[dict[str, Any]] = {
    "cover": {"roof": "single_glass", "walls": {"side_wall_left": TWIN_WALL}},
    "boundaries": {
        "end_wall_front": {"faces": "space", "kind": "corridor", "temperature_c": 12.0},
        "end_wall_back": {"faces": "space", "kind": "headhouse", "recording": "headhouse.csv"},
        "side_wall_right": {"faces": "nothing"},
        "side_wall_left": {"faces": "outside"},
    },
    "floor": {
        "surface": {"shortwave_reflectance": 0.5, "longwave_emissivity": 0.95},
        "layers": [
            {"thickness_m": 0.02, "material": "concrete"},
            {"thickness_m": 0.04, "material": "soil"},
            {
                "thickness_m": 0.64,
                "material": {"conductivity_w_m_k": 1.2, "volumetric_heat_capacity_j_m3_k": 2.5e6},
            },
        ],
        "deep_soil_temperature_c": 10.0,
    },
    "screens": [
        THERMAL_SCREEN,
        {
            "screen_id": "shade",
            "kind": "shading",
            "material": {
                "shortwave_transmittance": 0.5,
                "shortwave_reflectance": 0.4,
                "longwave_emissivity": 0.5,
                "longwave_transmittance": 0.4,
                "air_permeability_m3_m2_s_k": 5e-4,
                "thickness_m": 0.3e-3,
                "volumetric_heat_capacity_j_m3_k": 3.0e5,
            },
            "height_m": 3.8,
            "extent": {"start": {"x": 0.0, "y": 2.4}, "end": {"x": 12.0, "y": 2.4}, "width": 4.8},
            "closure": 0.5,
        },
    ],
    "pipe_networks": [RAIL_PIPES],
}


def _file(components: dict[str, Any] | None = None) -> dict[str, Any]:
    """The scenario's house as its file writes it, describing `components`,
    every one of them if none is named."""
    document: dict[str, Any] = json.loads(
        export_installation(scenario_installation(SCENARIO_REGISTRY[SCENARIO]))
    )
    return document | {
        "components": copy.deepcopy(COMPONENTS if components is None else components)
    }


def _house(components: dict[str, Any] | None = None) -> Installation:
    return import_installation(json.dumps(_file(components)))


def _with(document: dict[str, Any], path: str, value: object) -> dict[str, Any]:
    """`document` with the field at `path` (`a.b[0].c`) given `value`."""
    changed = copy.deepcopy(document)
    *above, last = path.replace("[", ".").replace("]", "").split(".")
    holder: Any = changed
    for key in above:
        holder = holder[int(key)] if key.isdigit() else holder[key]
    holder[int(last) if last.isdigit() else last] = value
    return changed


def _run(components: HouseComponents | None, house_air: str = "grid") -> ScenarioConfig:
    """The scenario, its house describing `components`, its air worked out by
    the model `house_air`."""
    config = SCENARIO_REGISTRY[SCENARIO]
    return ScenarioConfig.model_validate(
        config.model_dump() | {"components": components, "climate": {"kind": house_air}}
    )


def test_a_house_with_every_component_reads_back_the_same_from_its_file() -> None:
    house = _house()
    text = export_installation(house)

    assert import_installation(text) == house
    assert export_installation(import_installation(text)) == text
    assert json.loads(text)["components"] == COMPONENTS
    assert house.components is not None and house.components.floor is not None
    assert house.components.floor.depth_m == pytest.approx(0.70)


def test_a_house_with_every_component_reads_back_the_same_from_the_builders_answer() -> None:
    house = _house()

    answer = builder.assess(export_installation(house)).model_dump(mode="json")
    sent_back = {"schema_version": answer["schema_version"], **answer["installation"]}

    assert import_installation(json.dumps(sent_back)) == house
    # An edit keeps what it does not touch.
    same: dict[str, Any] = {"edit": "set_value", "path": "envelope.length", "value": 12.0}
    assert builder.edit({"file": sent_back, "edit": same}).installation == house
    removed = builder.edit(
        {"file": sent_back, "edit": {"edit": "remove_items", "items": ["heater"]}}
    )
    assert removed.installation.components == house.components


def test_a_house_that_describes_no_component_writes_none() -> None:
    for scenario_id in manifest_ids():
        config = SCENARIO_REGISTRY[scenario_id]
        installation = scenario_installation(config)

        assert config.components is None and installation.components is None
        # What a configuration's digest, and so a run's identity, is made of.
        assert "components" not in config.model_dump(mode="json")
        assert "components" not in json.loads(export_installation(installation))
    with pytest.raises(InstallationFileError, match="describes no component"):
        _house({})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("components.cover.walls.side_wall_left.longwave_emissivity", 1.2),
        ("components.cover.walls.side_wall_left.thickness_m", 0.0),
        ("components.cover.walls.side_wall_left.volumetric_heat_capacity_j_m3_k", 5.0e6),
        ("components.floor.surface.shortwave_reflectance", -0.1),
        ("components.floor.layers[0].thickness_m", -0.02),
        ("components.floor.layers[2].material.conductivity_w_m_k", 0.0),
        ("components.floor.deep_soil_temperature_c", 80.0),
        ("components.screens[0].closure", 1.5),
        ("components.screens[1].material.air_permeability_m3_m2_s_k", -1e-4),
        ("components.pipe_networks[0].longwave_emissivity", 1.01),
        ("components.pipe_networks[0].length_m", 0.0),
    ],
)
def test_a_value_outside_its_range_is_refused_by_its_field(field: str, value: float) -> None:
    with pytest.raises(InstallationFileError) as refused:
        import_installation(json.dumps(_with(_file(), field, value)))

    assert [problem.field for problem in refused.value.problems] == [field]


def test_a_wall_boundarys_value_is_refused_by_its_field_under_what_it_faces() -> None:
    """A tagged union's path names the case, as a layout's fixtures' do
    (`layout.placed[0].walkway.width`)."""
    written = "components.boundaries.end_wall_front.temperature_c"

    with pytest.raises(InstallationFileError) as refused:
        import_installation(json.dumps(_with(_file(), written, -70.0)))

    assert [problem.field for problem in refused.value.problems] == [
        "components.boundaries.end_wall_front.space.temperature_c"
    ]


def test_a_material_is_the_catalogues_by_its_name_and_a_name_it_has_not_is_refused() -> None:
    components = _house().components
    assert components is not None and components.cover is not None
    roof, wall = components.cover.roof, components.cover.walls["side_wall_left"]

    single_glass = COVER_MATERIALS[CoverMaterialName.SINGLE_GLASS].properties
    assert material(roof, COVER_MATERIALS) is single_glass
    assert material(wall, COVER_MATERIALS) == CoverMaterial(**TWIN_WALL)
    with pytest.raises(InstallationFileError) as refused:
        import_installation(json.dumps(_with(_file(), "components.cover.roof", "double_glass")))
    assert [problem.field for problem in refused.value.problems] == ["components.cover.roof"]
    assert "single_glass" in refused.value.problems[0].message


def test_what_a_material_passes_reflects_and_emits_adds_up_to_all_of_it_at_most() -> None:
    with pytest.raises(ValidationError, match="longwave_emissivity and longwave_transmittance"):
        CoverMaterial(**TWIN_WALL | {"longwave_emissivity": 0.7, "longwave_transmittance": 0.4})
    with pytest.raises(ValidationError, match="beam_transmittance and shortwave_reflectance"):
        CoverMaterial(**TWIN_WALL | {"shortwave_beam_transmittance": 0.9})
    # GreenLight's blackout screen emits 0.67 and passes 0.7 of the longwave,
    # 1.37 of it, which is why the catalogue does not name it.
    with pytest.raises(ValidationError, match=r"add up to 1\.37"):
        ScreenCloth(
            shortwave_transmittance=0.01,
            shortwave_reflectance=0.35,
            longwave_emissivity=0.67,
            longwave_transmittance=0.7,
            air_permeability_m3_m2_s_k=5e-5,
            thickness_m=0.35e-3,
            volumetric_heat_capacity_j_m3_k=3.6e5,
        )


def test_every_value_the_catalogue_gives_has_its_source() -> None:
    for catalogue in (COVER_MATERIALS, LAYER_MATERIALS, SCREEN_CLOTHS):
        for name, named in catalogue.items():
            fields = set(type(named.properties).model_fields)

            assert set(named.sources) == fields, name
            assert all(source.strip() for source in named.sources.values()), name


def test_the_catalogues_values_are_vanthoors() -> None:
    """Vanthoor (2011), Table 8.2, the Netherlands, worked by hand: each
    heat capacity its density times its specific heat."""
    glass = COVER_MATERIALS[CoverMaterialName.SINGLE_GLASS].properties
    assert (glass.shortwave_beam_transmittance, glass.longwave_emissivity) == (0.85, 0.85)
    assert glass.volumetric_heat_capacity_j_m3_k == 2600 * 840
    assert (glass.thickness_m, glass.conductivity_w_m_k) == (0.004, 1.05)
    # The diffuse is the sunlight's own, for single glass, to its rounding.
    assert glass.shortwave_diffuse_transmittance == pytest.approx(DIFFUSE_TRANSMITTANCE, abs=5e-4)
    assert LAYER_MATERIALS[LayerMaterialName.CONCRETE].properties == LayerMaterial(
        conductivity_w_m_k=1.7, volumetric_heat_capacity_j_m3_k=2300 * 880
    )
    assert LAYER_MATERIALS[LayerMaterialName.SOIL].properties == LayerMaterial(
        conductivity_w_m_k=0.85, volumetric_heat_capacity_j_m3_k=1.73e6
    )
    cloth = SCREEN_CLOTHS[ScreenClothName.THERMAL_SCREEN_CLOTH].properties
    assert cloth.volumetric_heat_capacity_j_m3_k == 200 * 1800
    assert (cloth.shortwave_transmittance, cloth.longwave_transmittance) == (0.6, 0.15)


@pytest.mark.parametrize(
    "space",
    [
        {"faces": "space", "kind": "corridor"},
        {"faces": "space", "kind": "corridor", "temperature_c": 12.0, "recording": "c.csv"},
        {"faces": "space", "kind": "corridor", "recording": "../weather/c.csv"},
        {"faces": "space", "kind": "barn", "temperature_c": 12.0},
    ],
)
def test_a_space_is_at_a_constant_or_a_recorded_temperature(space: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        OnASpace.model_validate(space)


@pytest.mark.parametrize(
    "components",
    [
        {"screens": [THERMAL_SCREEN | {"height_m": 4.01}]},
        {
            "screens": [
                THERMAL_SCREEN
                | {"extent": {"start": {"x": 0, "y": 5}, "end": {"x": 12, "y": 5}, "width": 9.7}}
            ]
        },
        {"pipe_networks": [RAIL_PIPES | {"height_m": 4.2}]},
    ],
    ids=["a screen above the eaves", "a screen wider than the floor", "pipes above the eaves"],
)
def test_what_does_not_fit_in_the_house_is_found_and_refused_a_run(
    components: dict[str, Any],
) -> None:
    draft = _house(components)
    assert draft.components is not None
    named = draft.components.names()

    outside = [f.items for f in assess_installation(draft) if f.code == "outside_envelope"]
    assert outside == [named]
    with pytest.raises(ValidationError, match=f"outside the greenhouse: {named[0]}"):
        _run(draft.components)


def test_screens_and_pipes_are_named_apart_from_one_another_and_the_houses_items() -> None:
    with pytest.raises(InstallationFileError, match="share an identifier: roof_vent_1"):
        _house({"screens": [THERMAL_SCREEN | {"screen_id": "roof_vent_1"}]})
    with pytest.raises(InstallationFileError, match="share an identifier: heater"):
        _house({"pipe_networks": [RAIL_PIPES | {"network_id": "heater"}]})
    with pytest.raises(InstallationFileError, match="share an identifier: rail_pipes"):
        _house(
            {
                "screens": [THERMAL_SCREEN | {"screen_id": "rail_pipes"}],
                "pipe_networks": [RAIL_PIPES],
            }
        )
    with pytest.raises(InstallationFileError, match="at least 1 item"):
        _house({"screens": []})


def test_a_pipe_is_hollow() -> None:
    with pytest.raises(InstallationFileError, match="not inside its outer"):
        _house({"pipe_networks": [RAIL_PIPES | {"inner_diameter_m": 0.051}]})


@pytest.mark.parametrize("house_air", ["grid", "whole_house"])
@pytest.mark.parametrize(
    ("components", "named"),
    [
        ({"screens": [THERMAL_SCREEN]}, "the thermal screen energy_screen"),
        ({"floor": COMPONENTS["floor"]}, "its floor"),
        ({"boundaries": {"end_wall_back": {"faces": "nothing"}}}, "end_wall_back on nothing"),
        (
            {"boundaries": {"end_wall_front": COMPONENTS["boundaries"]["end_wall_front"]}},
            "end_wall_front on a corridor",
        ),
        ({"pipe_networks": [RAIL_PIPES]}, "the rail pipes rail_pipes"),
    ],
)
def test_todays_models_refuse_a_house_they_cannot_model_naming_what_it_describes(
    house_air: str, components: dict[str, Any], named: str
) -> None:
    with pytest.raises(ValidationError) as refused:
        _run(_house(components).components, house_air)

    assert [error["msg"] for error in refused.value.errors()] == [
        f"Value error, its house air's model, {house_air}, cannot model {named}"
    ]


def test_a_manifest_of_a_house_with_a_screen_is_refused_under_the_whole_house() -> None:
    manifest = json.loads((MANIFESTS_DIR / f"{SCENARIO}.json").read_text())
    manifest["installation"]["components"] = {"screens": [THERMAL_SCREEN]}
    manifest["models"] = manifest.get("models", {}) | {"house_air": {"model": "whole_house"}}

    with pytest.raises(ValidationError, match="whole_house, cannot model the thermal screen"):
        scenario_from_manifest(SCENARIO, manifest)


def test_a_wall_on_the_outside_is_todays_and_runs() -> None:
    house = _house({"boundaries": {"side_wall_left": {"faces": "outside"}}})
    assert house.components is not None

    config = _run(house.components)

    assert config.components == house.components
    assert house.components.described() == []
    assert scenario_installation(config) == house


def test_a_refusal_names_three_of_what_it_cannot_model_and_counts_the_rest() -> None:
    components = _house().components
    assert components is not None

    with pytest.raises(
        ValidationError, match=r"cannot model end_wall_front on a corridor, .* and 4 more"
    ):
        _run(components)
    assert [kind for kind, _ in components.described()] == [
        Component.COVER,
        Component.WALL_ON_A_SPACE,
        Component.WALL_ON_A_SPACE,
        Component.WALL_ON_NOTHING,
        Component.FLOOR,
        Component.SCREEN,
        Component.SCREEN,
        Component.PIPE_NETWORK,
    ]
