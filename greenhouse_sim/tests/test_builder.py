"""An installation drafted, assessed, edited many rows at a time and
exchanged as a file (P12.0, decision 0050)."""

import json
import math

import pytest
from pydantic import ValidationError

from greenhouse_sim.builder.basic import BasicSetup, basic_installation
from greenhouse_sim.builder.batch import assign_crop_to_rows
from greenhouse_sim.builder.installation import (
    InstallationDraft,
    RowCrop,
    assess_installation,
)
from greenhouse_sim.builder.portable import (
    MAX_IMPORT_BYTES,
    InstallationFileError,
    export_installation,
    import_installation,
)
from greenhouse_sim.domain.crop import CropModel
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.scenarios.manifest_files import SCHEMA_VERSION


def _values(**changes: object) -> BasicSetup:
    data = {
        "installation_id": "my_greenhouse",
        "name": "Test house",
        "length_m": 12.0,
        "width_m": 6.0,
        "eave_height_m": 4.0,
        "ridge_height_m": 4.5,
        "spans": 2,
        "bays": 3,
        "rows": 2,
        "plants_per_row": 6,
        "plant_pitch_m": 0.75,
        "row_spacing_m": 1.6,
        "support_height_m": 0.6,
        "crop_model": "organ",
        "variety": "cherry_tomato",
    }
    return BasicSetup.model_validate(data | changes)


def _codes(draft: InstallationDraft) -> set[str]:
    return {finding.code for finding in assess_installation(draft)}


def test_the_first_form_drafts_a_house_with_its_planting_positions() -> None:
    draft = basic_installation(_values())

    assert (draft.envelope.length, draft.envelope.width, draft.envelope.spans) == (12, 6, 2)
    assert len(draft.layout.planting_positions()) == 12
    assert [(crop.row, crop.crop_model) for crop in draft.row_crops] == [
        (1, CropModel.ORGAN),
        (2, CropModel.ORGAN),
    ]
    assert not [f for f in assess_installation(draft) if f.severity == "error"]


def test_a_draft_without_a_door_vents_heater_or_fans_is_warned_not_refused() -> None:
    findings = assess_installation(basic_installation(_values()))

    assert {f.code for f in findings if f.severity == "warning"} == {
        "no_door",
        "no_vents",
        "no_heating",
        "no_fans",
    }


def test_a_packaged_scenarios_house_lacks_nothing() -> None:
    reference = SCENARIO_REGISTRY["reference_greenhouse"]
    rows = reference.layout.crop_rows
    assert rows is not None
    draft = InstallationDraft(
        installation_id="reference",
        name=reference.name,
        envelope=reference.envelope,
        layout=reference.layout,
        row_crops=[
            RowCrop(row=row, crop_model=reference.crop_model, variety=reference.variety)
            for row in range(1, rows.rows + 1)
        ],
    )

    assert assess_installation(draft) == []


def test_rows_of_different_crops_are_kept_but_said_not_to_run() -> None:
    draft = basic_installation(_values())
    mixed = draft.model_copy(
        update={
            "row_crops": [
                draft.row_crops[0],
                RowCrop(row=2, crop_model=CropModel.SIMPLE, variety="beefsteak"),
            ]
        }
    )

    (finding,) = [f for f in assess_installation(mixed) if f.code == "mixed_crops_not_runnable"]
    assert finding.rows == [1, 2]


def test_a_crop_is_one_the_simulator_grows() -> None:
    with pytest.raises(ValidationError, match="crop_model"):
        RowCrop(row=1, crop_model="tomato.simple", variety="cherry")


def test_what_reaches_through_a_wall_is_named_and_listed_whole() -> None:
    # Two rows of six, 3.75 m long, centred in a 4 m long house: each row's
    # gutter, its legs at either end and its slab reach through the gables.
    finding = next(
        f
        for f in assess_installation(basic_installation(_values(length_m=4.0)))
        if f.code == "outside_envelope"
    )

    assert len(finding.items) > 3
    first_three = ", ".join(finding.items[:3])
    assert finding.message == (
        f"Outside the greenhouse: {first_three} and {len(finding.items) - 3} more."
    )
    assert set(finding.items) >= {"row_1_support_1", "row_2_slab_1"}


def test_rows_without_a_crop_are_listed_by_number() -> None:
    draft = basic_installation(_values(rows=3))
    partial = draft.model_copy(update={"row_crops": [draft.row_crops[0]]})

    (finding,) = [f for f in assess_installation(partial) if f.code == "unassigned_rows"]
    assert finding.rows == [2, 3]
    assert finding.message == "No crop chosen for rows 2, 3."


def test_a_row_given_two_crops_or_none_of_the_layouts_is_refused() -> None:
    data = basic_installation(_values()).model_dump()

    with pytest.raises(ValidationError, match=r"row 1 has more than one crop, at \[0\] and \[2\]"):
        InstallationDraft.model_validate(data | {"row_crops": data["row_crops"] * 2})
    beyond = [{"row": 3, "crop_model": "organ", "variety": "cherry"}]
    with pytest.raises(ValidationError, match=r"rows \[3\], beyond the layout's 2 rows"):
        InstallationDraft.model_validate(data | {"row_crops": beyond})


@pytest.mark.parametrize(
    "changes",
    [
        {"length_m": 0},
        {"rows": 0},
        {"row_spacing_m": 0},
    ],
)
def test_the_form_refuses_a_size_no_house_has(changes: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        _values(**changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"ridge_height_m": 2.0},
        {"support_height_m": 0.05},
    ],
)
def test_the_draft_refuses_what_its_models_refuse(changes: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        basic_installation(_values(**changes))


def test_a_file_carries_the_manifests_format_and_reads_back_the_same() -> None:
    draft = basic_installation(_values())
    text = export_installation(draft)

    assert json.loads(text)["schema_version"] == SCHEMA_VERSION
    assert import_installation(text) == draft
    named = json.dumps({"$schema": "installation.schema.json", **json.loads(text)})
    assert import_installation(named) == draft


def test_a_file_refused_says_which_field_is_at_fault() -> None:
    document = json.loads(export_installation(basic_installation(_values())))
    document["envelope"]["length"] = -1
    document["row_crops"][1]["crop_model"] = "tomato.simple"

    with pytest.raises(InstallationFileError) as refused:
        import_installation(json.dumps(document))

    assert [problem.field for problem in refused.value.problems] == [
        "envelope.length",
        "row_crops[1].crop_model",
    ]
    assert str(refused.value).startswith("not a greenhouse installation file: envelope.length:")
    assert str(refused.value).endswith("(and 1 more)")


@pytest.mark.parametrize(
    ("text", "field", "said"),
    [
        ("{not json}", "", "not JSON"),
        ("[1, 2]", "", "not a JSON object"),
        ('{"unexpected": "document"}', "schema_version", "format None"),
        (json.dumps({"schema_version": SCHEMA_VERSION + 1}), "schema_version", "format"),
        (json.dumps({"schema_version": True}), "schema_version", "format True"),
        (" " * (MAX_IMPORT_BYTES + 1), "", "larger than"),
    ],
    ids=["not json", "not an object", "no version", "a later version", "a boolean", "too large"],
)
def test_a_file_that_is_no_installation_is_refused(text: str, field: str, said: str) -> None:
    with pytest.raises(InstallationFileError) as refused:
        import_installation(text)

    (problem,) = refused.value.problems
    assert (problem.field, said in problem.message) == (field, True)


def test_a_file_giving_a_row_two_crops_says_where() -> None:
    document = json.loads(export_installation(basic_installation(_values())))
    document["row_crops"].append(document["row_crops"][0])

    with pytest.raises(InstallationFileError) as refused:
        import_installation(json.dumps(document))

    (problem,) = refused.value.problems
    assert problem.field == "row_crops"
    assert "row 1 has more than one crop, at [0] and [2]" in problem.message


@pytest.mark.parametrize(
    ("part", "field"),
    [
        # `Envelope` and `Vector3` ignore a field they do not have.
        (("envelope",), "envelope.colour"),
        (("envelope", "origin", "position"), "envelope.origin.position.colour"),
        # `RowSupport` refuses one itself.
        (("layout", "crop_rows", "support"), "layout.crop_rows.support.colour"),
    ],
)
def test_a_field_no_model_of_a_draft_has_is_refused_by_its_path(
    part: tuple[str, ...], field: str
) -> None:
    document = json.loads(export_installation(basic_installation(_values())))
    holder = document
    for key in part:
        holder = holder[key]
    holder["colour"] = "green"

    with pytest.raises(InstallationFileError) as refused:
        import_installation(json.dumps(document))

    assert [problem.field for problem in refused.value.problems] == [field]


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"rows": 10**9}, "layout.crop_rows.rows"),
        ({"positions_per_row": 10**9}, "layout.crop_rows.positions_per_row"),
    ],
)
def test_a_small_file_asking_for_a_crop_too_large_is_refused_before_it_is_laid_out(
    changes: dict[str, int], field: str
) -> None:
    document = json.loads(export_installation(basic_installation(_values())))
    document["layout"]["crop_rows"] |= changes
    document["row_crops"] = []

    with pytest.raises(InstallationFileError) as refused:
        import_installation(json.dumps(document))

    assert [problem.field for problem in refused.value.problems] == [field]


def test_a_file_whose_support_is_too_short_for_two_legs_reads() -> None:
    # 2 cm long, less than its two end legs' 4 cm.
    document = json.loads(export_installation(basic_installation(_values(plants_per_row=1))))
    support = document["layout"]["crop_rows"]["support"]
    support |= {"overhang": 0.01, "leg_spacing": 1.0, "slab": None}

    draft = import_installation(json.dumps(document))

    legs = [f for f in draft.layout.fixtures() if f.fixture_id.startswith("row_1_support_1_leg")]
    assert len(legs) == 1


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_a_number_json_has_not_is_refused(constant: str) -> None:
    text = export_installation(basic_installation(_values()))
    text = text.replace('"length": 12.0', f'"length": {constant}', 1)

    with pytest.raises(InstallationFileError, match=f"not JSON: {constant} is not a JSON number"):
        import_installation(text)


def test_a_draft_holding_a_number_json_has_not_is_not_written() -> None:
    draft = basic_installation(_values())
    origin = draft.envelope.origin
    odd = draft.model_copy(
        update={
            "envelope": draft.envelope.model_copy(
                update={
                    "origin": origin.model_copy(
                        update={"position": origin.position.model_copy(update={"x": math.nan})}
                    )
                }
            )
        }
    )

    with pytest.raises(ValueError, match="Out of range float values are not JSON compliant"):
        export_installation(odd)


def test_a_file_with_a_field_no_draft_has_is_refused() -> None:
    document = json.loads(export_installation(basic_installation(_values())))

    with pytest.raises(InstallationFileError) as refused:
        import_installation(json.dumps(document | {"weather": "default"}))

    assert [problem.field for problem in refused.value.problems] == ["weather"]


def test_a_crop_given_to_chosen_rows_leaves_the_others() -> None:
    draft = basic_installation(_values(rows=3))
    changed = assign_crop_to_rows(
        draft, [3, 2, 2], crop_model=CropModel.SIMPLE, variety="beefsteak"
    )

    assert changed.row_crops[0] == draft.row_crops[0]
    assert [crop.variety for crop in changed.row_crops] == [
        "cherry_tomato",
        "beefsteak",
        "beefsteak",
    ]
    again = assign_crop_to_rows(changed, [2, 3], crop_model=CropModel.SIMPLE, variety="beefsteak")
    assert again == changed


@pytest.mark.parametrize(
    ("rows", "crop_model", "said"),
    [
        ([1, 4], CropModel.SIMPLE, "from 1 to 3"),
        ([], CropModel.SIMPLE, "at least one"),
        ([True], CropModel.SIMPLE, "by their numbers"),
        ([1, 2], "tomato.simple", "crop_model"),
    ],
)
def test_a_crop_given_to_rows_changes_nothing_when_refused(
    rows: list[int], crop_model: CropModel, said: str
) -> None:
    draft = basic_installation(_values(rows=3))
    before = draft.model_dump_json()

    with pytest.raises(ValueError, match=said):
        assign_crop_to_rows(draft, rows, crop_model=crop_model, variety="beefsteak")
    assert draft.model_dump_json() == before
