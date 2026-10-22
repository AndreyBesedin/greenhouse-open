import pytest
from pydantic import ValidationError

from greenhouse_sim.builder.basic import BasicSetup, basic_installation
from greenhouse_sim.builder.installation import InstallationDraft, RowCrop, assess_installation


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
        "model_id": "tomato.organ",
        "variety": "cherry_tomato",
    }
    return BasicSetup.model_validate(data | changes)


def test_basic_form_creates_a_portable_draft_with_real_plant_positions() -> None:
    draft = basic_installation(_values())

    assert (draft.envelope.length, draft.envelope.width, draft.envelope.spans) == (12, 6, 2)
    assert draft.layout.crop_rows is not None
    assert len(draft.layout.planting_positions()) == 12
    assert [crop.row for crop in draft.row_crops] == [1, 2]
    assert not [finding for finding in assess_installation(draft) if finding.severity == "error"]
    assert InstallationDraft.model_validate_json(draft.model_dump_json()) == draft


def test_first_preview_warns_about_optional_equipment_instead_of_refusing_it() -> None:
    findings = assess_installation(basic_installation(_values()))
    warnings = {finding.code for finding in findings if finding.severity == "warning"}

    assert {"no_door", "no_vents", "no_heating", "no_fans"} <= warnings


def test_draft_can_assign_different_crops_to_rows_but_not_claim_run_support() -> None:
    draft = basic_installation(_values())
    changed = draft.model_copy(
        update={
            "row_crops": [
                draft.row_crops[0],
                RowCrop(row=2, model_id="tomato.simple", variety="beefsteak"),
            ]
        }
    )

    assert "mixed_crops_not_runnable" in {finding.code for finding in assess_installation(changed)}


def test_rows_that_extend_beyond_envelope_are_reported() -> None:
    draft = basic_installation(_values(length_m=4.0))
    codes = {finding.code for finding in assess_installation(draft)}

    assert "outside_envelope" in codes


def test_missing_row_crops_are_draft_errors() -> None:
    draft = basic_installation(_values())
    changed = draft.model_copy(update={"row_crops": [draft.row_crops[0]]})

    assert "unassigned_rows" in {finding.code for finding in assess_installation(changed)}


def test_invalid_row_assignment_is_refused_at_the_document_boundary() -> None:
    draft = basic_installation(_values())
    data = draft.model_dump()
    data["row_crops"].append(data["row_crops"][0])

    with pytest.raises(ValidationError, match="more than one crop"):
        InstallationDraft.model_validate(data)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("length_m", 0),
        ("rows", 0),
        ("row_spacing_m", 0),
        ("ridge_height_m", 2.0),
        ("support_height_m", 0.05),
    ],
)
def test_basic_form_rejects_impossible_sizes(field: str, value: float) -> None:
    if field in {"length_m", "rows", "row_spacing_m"}:
        with pytest.raises(ValidationError):
            _values(**{field: value})
    else:
        with pytest.raises(ValidationError):
            basic_installation(_values(**{field: value}))
