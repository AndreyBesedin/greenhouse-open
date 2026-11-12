"""A crop model's parameter set as a file (P20.2, decision 0077): read and
checked, resolved against its base, told apart by its digest and compared
with another; the published sets as sets, their digests pinned."""

from typing import Any, Final

import pytest
from pydantic import JsonValue

from greenhouse_sim.biology.parameter_sets import (
    PARAMETER_MODELS,
    PUBLISHED_SETS,
    InvalidParameterSet,
    ParameterChange,
    ParameterSet,
    compared,
    read_parameter_set,
    resolved,
)
from greenhouse_sim.biology.tomato.tomgro.parameters import TomgroParameters
from greenhouse_sim.biology.tomato.vanthoor.parameters import VanthoorParameters
from greenhouse_sim.domain.parts import Part
from greenhouse_sim.scenarios.crop_parameters import ReducedTomgroCrop, VanthoorKatzinCrop
from greenhouse_sim.scenarios.registry import MODELS, model

TOMGRO: Final = "reduced_tomgro"
VANTHOOR: Final = "vanthoor_katzin"
# Each published set's digest, by its model and the model's version. A
# published default changed while its model's version stays the same fails
# here: a model's numbers change with its version (decision 0077).
PINNED: Final = {
    (TOMGRO, 1): "sha256:2c83ead72f5e26a13a16bc1caea6853cdd63598faa7f92613580d3d78123c168",
    (VANTHOOR, 1): "sha256:4a0593e96cb0daae94d7286255dc52406173fdc7cf36af905d0eba87a05f8978",
}
# Decision 0076's calibration of Reduced-State TOMGRO, its four values as
# committed (`research/validation/agc4/calibrated/tomgro.json`).
CALIBRATED: Final = {
    "n_ff": 10.134414960024458,
    "delta": 0.019476494220825327,
    "qe": 0.0998254275506692,
    "alpha_f": 0.9982485362609262,
}


def _published_named(model_name: str) -> dict[str, JsonValue]:
    published = resolved(PUBLISHED_SETS[model_name])
    named: dict[str, JsonValue] = published.named.model_dump(mode="json")
    return named


def _file(**changed: Any) -> dict[str, JsonValue]:
    """A set of Reduced-State TOMGRO's based on its published one, as its
    file gives it: decision 0076's calibration, with `changed` over it."""
    document: dict[str, JsonValue] = {
        "model": TOMGRO,
        "name": "agc4_pretrial_2023",
        "version": 1,
        "based_on": _published_named(TOMGRO),
        "parameters": dict(CALIBRATED),
        "why": dict.fromkeys(CALIBRATED, "decision 0076's calibration on AGC4's pre-trial"),
        "made_for": 1,
        "cultivar": None,
        "description": "",
    }
    return document | changed


def _refused(document: dict[str, JsonValue], *known: ParameterSet) -> dict[str, str]:
    with pytest.raises(InvalidParameterSet) as refused:
        resolved(read_parameter_set(document), {_key(each): each for each in known})
    return refused.value.problems


def _key(parameter_set: ParameterSet) -> tuple[str, str, int]:
    return parameter_set.model, parameter_set.name, parameter_set.version


@pytest.mark.parametrize("model_name", sorted(PARAMETER_MODELS))
def test_a_published_set_s_digest_is_pinned_for_its_model_s_version(model_name: str) -> None:
    version = model(Part.CROP, model_name).version

    assert resolved(PUBLISHED_SETS[model_name]).digest == PINNED[(model_name, version)], (
        f"{model_name}'s published numbers changed: its model's version changes with them"
    )


@pytest.mark.parametrize("model_name", sorted(PARAMETER_MODELS))
def test_a_published_set_is_its_model_s_defaults_read_back_from_its_file(
    model_name: str,
) -> None:
    published = PUBLISHED_SETS[model_name]
    read = read_parameter_set(published.model_dump(mode="json"))

    assert read == published
    assert published.based_on is None
    assert published.version == 1
    assert published.made_for == model(Part.CROP, model_name).version
    assert resolved(read).values == PARAMETER_MODELS[model_name]()


def test_the_published_sets_are_the_ones_the_crop_sections_name() -> None:
    assert PUBLISHED_SETS[TOMGRO].name == ReducedTomgroCrop().parameter_set
    assert PUBLISHED_SETS[VANTHOOR].name == VanthoorKatzinCrop().parameter_set
    assert set(PARAMETER_MODELS) <= set(MODELS[Part.CROP])


def test_a_set_based_on_a_published_one_resolves_to_its_values_over_its_base_s() -> None:
    calibrated = resolved(read_parameter_set(_file()))

    assert calibrated.values == TomgroParameters().model_copy(update=CALIBRATED)
    assert calibrated.digest != resolved(PUBLISHED_SETS[TOMGRO]).digest


def test_a_digest_is_of_the_numbers_alone() -> None:
    calibrated = resolved(read_parameter_set(_file()))
    renamed = resolved(
        read_parameter_set(_file(name="another", version=4, description="the same numbers"))
    )
    whole = resolved(
        read_parameter_set(
            _file(
                based_on=None,
                parameters=calibrated.values.model_dump(),
                why=dict.fromkeys(TomgroParameters.model_fields, "the calibration's"),
            )
        )
    )

    assert renamed.digest == calibrated.digest
    assert whole.digest == calibrated.digest


def test_a_set_may_be_based_on_another_that_is_known() -> None:
    calibrated = read_parameter_set(_file())
    named = resolved(calibrated).named.model_dump(mode="json")
    corrected = _file(
        name="agc4_pretrial_2023_denser",
        based_on=named,
        parameters={"ro": 4.0},
        why={"ro": "the trial's density"},
    )

    values = resolved(read_parameter_set(corrected), {_key(calibrated): calibrated}).values

    assert values == TomgroParameters().model_copy(update=CALIBRATED | {"ro": 4.0})


def test_a_known_set_never_stands_for_a_published_one() -> None:
    impostor = PUBLISHED_SETS[TOMGRO].model_copy(
        update={"parameters": PUBLISHED_SETS[TOMGRO].parameters | {"k": 0.9}}
    )

    assert (
        resolved(read_parameter_set(_file()), {_key(impostor): impostor}).values.model_dump()["k"]
        == 0.58
    )


@pytest.mark.parametrize(
    ("changed", "field"),
    [
        ({"m": 1.0}, "parameters.m"),
        ({"alpha_f": 1.2}, "parameters.alpha_f"),
        ({"k": -0.1}, "parameters.k"),
    ],
)
def test_a_value_outside_its_range_is_refused_by_its_field(
    changed: dict[str, float], field: str
) -> None:
    problems = _refused(
        _file(parameters=CALIBRATED | changed, why=dict.fromkeys(CALIBRATED | changed, "a guess"))
    )

    assert list(problems) == [field]


def test_a_pair_out_of_order_is_refused_naming_both() -> None:
    document: dict[str, JsonValue] = {
        "model": VANTHOOR,
        "name": "warm",
        "version": 1,
        "based_on": _published_named(VANTHOOR),
        "parameters": {"t_can_min": 36.0},
        "why": {"t_can_min": "a guess"},
        "made_for": 1,
        "cultivar": "Merlice",
    }

    problems = _refused(document)

    assert list(problems) == ["parameters"]
    assert "t_can_min (36) is not below t_can_max (34)" in problems["parameters"]


@pytest.mark.parametrize(
    ("changed", "problems"),
    [
        (
            {"parameters": {"trgh": 0.7}, "why": {"trgh": "the cover"}},
            {"parameters.trgh": "fixed at 1: no set changes it"},
        ),
        (
            {"parameters": {"leaves": 3.0}, "why": {"leaves": "a guess"}},
            {"parameters.leaves": "not a parameter of reduced_tomgro"},
        ),
        (
            {"why": {"n_ff": "the calibration"}},
            {
                f"why.{name}": "a value it changes says where it comes from"
                for name in ("delta", "qe", "alpha_f")
            },
        ),
        (
            {"why": dict.fromkeys([*CALIBRATED, "k"], "the calibration")},
            {"why.k": "says where a value comes from that the set does not change"},
        ),
    ],
)
def test_a_set_is_refused_by_field_as_it_stands(
    changed: dict[str, JsonValue], problems: dict[str, str]
) -> None:
    with pytest.raises(InvalidParameterSet) as refused:
        read_parameter_set(_file(**changed))

    assert refused.value.problems == problems


def test_a_fixed_parameter_at_its_published_value_is_kept() -> None:
    read = read_parameter_set(
        _file(parameters=CALIBRATED | {"d": 2.5926912}, why=dict.fromkeys([*CALIBRATED, "d"], "x"))
    )

    assert resolved(read).values.model_dump()["d"] == TomgroParameters().d


def test_a_set_based_on_none_gives_every_value() -> None:
    with pytest.raises(InvalidParameterSet) as refused:
        read_parameter_set(_file(based_on=None))

    assert list(refused.value.problems) == ["parameters"]
    assert refused.value.problems["parameters"].startswith("a set based on none gives every value")


@pytest.mark.parametrize(
    ("changed", "field"),
    [
        ({"model": "organ"}, "model"),
        ({"version": 0}, "version"),
        ({"name": "Not A Name"}, "name"),
        ({"parameters": {"n_ff": "many"}}, "parameters.n_ff"),
        ({"cultivar": 3}, "cultivar"),
        ({"colour": "red"}, "colour"),
    ],
)
def test_a_file_not_in_a_set_s_form_is_refused_by_field(
    changed: dict[str, JsonValue], field: str
) -> None:
    with pytest.raises(InvalidParameterSet) as refused:
        read_parameter_set(_file(**changed))

    assert field in refused.value.problems


def test_a_base_not_known_is_refused() -> None:
    based_on = _published_named(TOMGRO) | {"name": "elsewhere"}

    assert _refused(_file(based_on=based_on)) == {
        "based_on": "no set elsewhere v1 of reduced_tomgro is known"
    }


def test_a_base_of_other_numbers_than_its_digest_is_refused() -> None:
    based_on = _published_named(TOMGRO) | {"digest": "sha256:" + "0" * 64}

    assert list(_refused(_file(based_on=based_on))) == ["based_on.digest"]


def test_a_line_of_bases_that_comes_back_is_refused() -> None:
    digest = "sha256:" + "1" * 64
    first = read_parameter_set(
        _file(name="first", based_on={"name": "second", "version": 1, "digest": digest})
    )
    second = read_parameter_set(
        _file(name="second", based_on={"name": "first", "version": 1, "digest": digest})
    )

    with pytest.raises(InvalidParameterSet) as refused:
        resolved(first, {_key(first): first, _key(second): second})

    assert refused.value.problems == {"based_on": "its line of bases comes back to it"}


def test_two_sets_are_compared_parameter_by_parameter() -> None:
    published = resolved(PUBLISHED_SETS[TOMGRO])
    calibrated = resolved(read_parameter_set(_file()))

    assert compared(published, calibrated) == [
        ParameterChange(name=name, first=getattr(published.values, name), second=value)
        for name, value in sorted(
            CALIBRATED.items(), key=lambda item: list(TomgroParameters.model_fields).index(item[0])
        )
    ]
    assert compared(calibrated, calibrated) == []


def test_sets_of_different_models_are_not_compared() -> None:
    with pytest.raises(InvalidParameterSet) as refused:
        compared(resolved(PUBLISHED_SETS[TOMGRO]), resolved(PUBLISHED_SETS[VANTHOOR]))

    assert list(refused.value.problems) == ["model"]


def test_vanthoor_s_published_set_keeps_its_pairs_in_order() -> None:
    values = resolved(PUBLISHED_SETS[VANTHOOR]).values

    assert isinstance(values, VanthoorParameters)
    assert values.t_can_min < values.t_can_max
