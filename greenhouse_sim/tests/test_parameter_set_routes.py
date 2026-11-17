"""A crop model's parameter sets, kept and served (P20.4, decision 0077):
listed, read, saved, compared, downloaded and uploaded through the API. The
same numbers saved twice are one version; a value outside its range is
refused by field; a name and version kept with another digest is refused."""

import json
from collections.abc import Iterator
from http import HTTPStatus
from pathlib import Path
from typing import Any, Final

import pytest
from pydantic import JsonValue

from greenhouse_sim.api.routes import respond
from greenhouse_sim.biology.parameter_sets import PUBLISHED_SETS, resolved
from greenhouse_sim.services.parameter_set_library import SetComparison, SetListed, SetRead
from greenhouse_sim.services.run_store import FolderStore
from greenhouse_sim.services.simulator import Simulator

TOMGRO: Final = "reduced_tomgro"
SETS: Final = f"/api/parameter-sets/{TOMGRO}"
PUBLISHED_DIGEST: Final = resolved(PUBLISHED_SETS[TOMGRO]).digest


def _set(name: str = "brighter", **values: float) -> dict[str, JsonValue]:
    """A set of Reduced-State TOMGRO's based on its published one, without a
    version, as a save sends it."""
    changed = values or {"qe": 0.1}
    return {
        "model": TOMGRO,
        "name": name,
        "based_on": resolved(PUBLISHED_SETS[TOMGRO]).named.model_dump(mode="json"),
        "parameters": dict(changed),
        "why": dict.fromkeys(changed, "a test's"),
        "made_for": 1,
        "cultivar": None,
        "description": "",
    }


@pytest.fixture
def simulator(tmp_path: Path) -> Iterator[Simulator]:
    with Simulator(runs=FolderStore(tmp_path)) as made:
        yield made


def _ok(simulator: Simulator, method: str, path: str, body: Any = None) -> Any:
    sent = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    answer = respond(simulator, method, path, sent)
    assert answer.status == HTTPStatus.OK, answer.body
    return answer.body


def _refused(simulator: Simulator, method: str, path: str, body: Any = None) -> Any:
    sent = b"" if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    return respond(simulator, method, path, sent)


def test_the_same_numbers_saved_twice_are_one_version(simulator: Simulator) -> None:
    first = SetListed.model_validate(_ok(simulator, "POST", SETS, _set()))
    again = SetListed.model_validate(_ok(simulator, "POST", SETS, _set()))
    other = SetListed.model_validate(_ok(simulator, "POST", SETS, _set(qe=0.12)))
    back = SetListed.model_validate(_ok(simulator, "POST", SETS, _set()))

    assert (first.version, again, back) == (1, first, first)
    assert (other.version, other.name) == (2, "brighter") and other.digest != first.digest
    listed = [SetListed.model_validate(each) for each in _ok(simulator, "GET", SETS)]
    assert [(each.name, each.version, each.published) for each in listed] == [
        ("gnvman", 1, True),
        ("brighter", 1, False),
        ("brighter", 2, False),
    ]
    assert listed[0].digest == PUBLISHED_DIGEST


def test_a_set_is_read_with_every_value_it_resolves_to_and_compared(
    simulator: Simulator,
) -> None:
    _ok(simulator, "POST", SETS, _set())

    read = SetRead.model_validate(_ok(simulator, "GET", f"{SETS}/brighter/1"))
    compared = SetComparison.model_validate(
        _ok(simulator, "GET", f"{SETS}/gnvman/1/compare/brighter/1")
    )

    assert read.parameters == {"qe": 0.1} and read.values["qe"] == 0.1
    assert read.values["lai_max"] == PUBLISHED_SETS[TOMGRO].parameters["lai_max"]
    assert [(c.name, c.first, c.second) for c in compared.changes] == [("qe", 0.08, 0.1)]
    assert (compared.first.digest, compared.second.digest) == (PUBLISHED_DIGEST, read.digest)
    assert _refused(simulator, "GET", f"{SETS}/brighter/2").status == HTTPStatus.NOT_FOUND
    assert _refused(simulator, "GET", f"{SETS}/brighter/one").status == HTTPStatus.BAD_REQUEST
    assert _refused(simulator, "GET", "/api/parameter-sets/organ").status == HTTPStatus.NOT_FOUND
    assert _refused(simulator, "POST", "/api/parameter-sets/organ", _set()).status == (
        HTTPStatus.NOT_FOUND
    )


def test_a_value_outside_its_range_is_refused_by_field(simulator: Simulator) -> None:
    answer = _refused(simulator, "POST", SETS, _set(lai_max=-1.0, qe=-0.1))

    assert answer.status == HTTPStatus.BAD_REQUEST
    assert sorted(problem["field"] for problem in answer.body["problems"]) == [
        "parameters.lai_max",
        "parameters.qe",
    ]
    assert len(_ok(simulator, "GET", SETS)) == 1
    # A save names no version; one of another model's, under the published
    # set's name or changing a fixed parameter is refused by field.
    for sent, field in (
        (_set(d=2.0), "parameters.d"),
        (_set() | {"version": 3}, "version"),
        (_set() | {"model": "vanthoor_katzin"}, "model"),
        (_set(name="gnvman"), "name"),
    ):
        refused = _refused(simulator, "POST", SETS, sent)
        assert refused.status == HTTPStatus.BAD_REQUEST
        assert [problem["field"] for problem in refused.body["problems"]] == [field]


def test_a_downloaded_set_uploads_as_itself_and_another_digest_is_refused(
    tmp_path: Path, simulator: Simulator
) -> None:
    saved = SetListed.model_validate(_ok(simulator, "POST", SETS, _set()))
    download = _ok(simulator, "GET", f"{SETS}/brighter/1/file")
    text: str = download["text"]

    assert download["file_name"] == "reduced_tomgro.brighter.v1.parameter_set.json"
    assert (
        SetListed.model_validate(
            _ok(simulator, "POST", "/api/parameter-sets/upload", text.encode())
        )
        == saved
    )
    with Simulator(runs=FolderStore(tmp_path / "fresh")) as fresh:
        assert (
            SetListed.model_validate(
                _ok(fresh, "POST", "/api/parameter-sets/upload", text.encode())
            )
            == saved
        )
    # A simulator that saved a brighter v1 of its own, with other numbers,
    # refuses this one: the same name and version, another digest.
    with Simulator(runs=FolderStore(tmp_path / "elsewhere")) as elsewhere:
        _ok(elsewhere, "POST", SETS, _set(qe=0.09))
        refused = _refused(elsewhere, "POST", "/api/parameter-sets/upload", text.encode())
        assert refused.status == HTTPStatus.CONFLICT, refused.body
    published = _ok(simulator, "GET", f"{SETS}/gnvman/1/file")["text"]
    assert _ok(simulator, "POST", "/api/parameter-sets/upload", published.encode())["published"]
    assert _refused(simulator, "POST", "/api/parameter-sets/upload", b"[]").status == (
        HTTPStatus.BAD_REQUEST
    )


def test_a_simulator_without_a_store_serves_its_published_sets_and_keeps_none() -> None:
    with Simulator() as simulator:
        (listed,) = _ok(simulator, "GET", SETS)
        assert listed["name"] == "gnvman"
        assert _refused(simulator, "POST", SETS, _set()).status == HTTPStatus.NOT_FOUND
