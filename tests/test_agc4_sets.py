"""Decision 0076's calibrated parameters as crop parameter sets (decision
0077): each committed set is its calibration's report, its values are those
the test on 2024 ran, and its digest is the one the README cites. No data
needed."""

import json

import pytest
from greenhouse_sim.biology.parameter_sets import (
    PUBLISHED_SETS,
    compared,
    read_parameter_set,
    resolved,
)

from research.validation.agc4 import sets
from research.validation.agc4.calibrate import MODELS
from research.validation.agc4.challenge import calibrated

# Each calibrated set's digest, as the README cites it. A change to a
# calibration's report, or to its model's published set, moves it.
DIGESTS = {
    "tomgro": "sha256:7a1162b8b0959d76504ad93fb5eabbf9b255e10964d1acae37295aa64d0c04fd",
    "vanthoor_katzin": "sha256:28572d6877e1459efda05b5e0559c65406cca8dcfd27ce78cfb4928889b98858",
}


@pytest.mark.parametrize("name", sorted(MODELS))
def test_a_committed_set_is_written_from_its_calibrations_report(name: str) -> None:
    model = MODELS[name]

    assert sets.path(model).read_text() == sets.written(sets.calibrated_set(model))


@pytest.mark.parametrize("name", sorted(MODELS))
def test_a_set_resolves_to_the_values_the_test_on_2024_ran(name: str) -> None:
    model = MODELS[name]
    committed = read_parameter_set(json.loads(sets.path(model).read_text()))

    found = resolved(committed)

    # challenge.py runs the published parameters with the report's over them.
    ran = model.published.model_copy(update=calibrated(model))
    assert found.values.model_dump() == ran.model_dump()
    assert found.digest == DIGESTS[name]


@pytest.mark.parametrize("name", sorted(MODELS))
def test_a_set_changes_from_its_published_set_only_what_was_calibrated(name: str) -> None:
    model = MODELS[name]
    found = sets.calibrated_sets()[name]
    published = resolved(PUBLISHED_SETS[sets.REGISTERED[name]])

    changed = {change.name for change in compared(published, found)}

    assert changed == {each["name"] for each in sets.report(model)["parameters"]}
    assert found.parameter_set.based_on == published.named
