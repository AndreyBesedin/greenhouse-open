"""A run under a crop parameter set (P20.3, decision 0077): the set its
crop section names, by name and version, looked up among the published sets
and those its simulator keeps, grows the same numbers when its run is
repeated and others than the published set's; the run is told apart by the
set's digest, and its manifest answer names the set; a run under a
published set is named as it was, and the packaged scenarios run only
those."""

import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Final

import pytest
from pydantic import JsonValue

from greenhouse_sim.biology.parameter_sets import PUBLISHED_SETS, read_parameter_set, resolved
from greenhouse_sim.biology.tomato.tomgro.parameters import TomgroParameters
from greenhouse_sim.core.area_crop import AreaCrop
from greenhouse_sim.core.tomgro_crop import TomgroRung
from greenhouse_sim.scenarios import manifest_files
from greenhouse_sim.scenarios.catalogue import PACKAGED
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.crop_parameters import (
    ReducedTomgroCrop,
    VanthoorKatzinCrop,
    runs_published,
)
from greenhouse_sim.scenarios.manifest_files import InvalidManifest, load_manifest
from greenhouse_sim.scenarios.scenario_files import export_scenario_file
from greenhouse_sim.services import scenario_files
from greenhouse_sim.services.crop import scenario_crop
from greenhouse_sim.services.crop_models import registration
from greenhouse_sim.services.errors import Conflict, InvalidRequest
from greenhouse_sim.services.fields import air_through_a_run
from greenhouse_sim.services.parameter_sets import SetRun, keep, kept_name
from greenhouse_sim.services.run_store import FolderStore
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.scenarios import run_manifest
from greenhouse_sim.services.simulator import Simulator

sys.path.insert(0, str(Path(__file__).parent))

from short_runs import cut

TOMGRO: Final = "reduced_tomgro"
HOUSE: Final = "house_under_a_set"
DAYS: Final = 1
# A quantum efficiency other than the published 0.08, which grows another
# canopy from a run's first day.
QUANTUM_EFFICIENCY: Final = 0.1


def _set(name: str = "brighter", version: int = 1, **values: float) -> dict[str, JsonValue]:
    """A set of Reduced-State TOMGRO's based on its published one, changing
    `values`, by default its quantum efficiency, as its file gives it."""
    changed = values or {"qe": QUANTUM_EFFICIENCY}
    return {
        "model": TOMGRO,
        "name": name,
        "version": version,
        "based_on": resolved(PUBLISHED_SETS[TOMGRO]).named.model_dump(mode="json"),
        "parameters": dict(changed),
        "why": dict.fromkeys(changed, "a test's"),
        "made_for": 1,
        "cultivar": None,
        "description": "",
    }


def _whole(name: str, **values: float) -> dict[str, JsonValue]:
    """A set of Reduced-State TOMGRO's based on none, its published values
    with `values` over them."""
    every = TomgroParameters().model_dump() | values
    return _set(name=name, **every) | {"based_on": None}


def _house(**section: Any) -> ScenarioConfig:
    """The TOMGRO house's first days, registered as a scenario of its own,
    its crop section `section`."""
    config = cut("tomgro_house", days=DAYS, season=True)
    return config.model_copy(update={"greenhouse_id": HOUSE, "crop": ReducedTomgroCrop(**section)})


@pytest.fixture
def store(tmp_path: Path) -> FolderStore:
    return FolderStore(tmp_path)


@contextmanager
def _uploaded(store: FolderStore, **section: Any) -> Iterator[Simulator]:
    """A simulator on `store` that registered the house under `section` from
    its file, as an upload does."""
    with Simulator(runs=store) as simulator:
        scenario_files.upload(simulator, export_scenario_file(_house(**section)))
        yield simulator


def _grown(store: FolderStore, **section: Any) -> tuple[str, tuple[Any, ...]]:
    """The run id of the house under `section`, uploaded to a simulator on
    `store`, and its canopies on its last day."""
    with _uploaded(store, **section) as simulator:
        crop = scenario_crop(simulator, RunRequest(HOUSE))
        assert isinstance(crop, AreaCrop)
        return air_through_a_run(simulator, RunRequest(HOUSE))[1], crop.instances_on(DAYS)


def test_a_run_under_a_set_grows_the_same_when_repeated_and_not_as_the_published(
    store: FolderStore,
) -> None:
    keep(store, _set())

    run_id, grown = _grown(store, parameter_set="brighter")
    again_id, again = _grown(store, parameter_set="brighter")
    published_id, published = _grown(FolderStore(store.root / "other"))

    assert (again_id, again) == (run_id, grown)
    assert published_id != run_id
    assert all(
        under.state.w > as_published.state.w
        for under, as_published in zip(grown, published, strict=True)
    )


def test_a_run_is_told_apart_by_its_sets_digest_not_its_name(store: FolderStore) -> None:
    """Two simulators that each keep a set of one name and version with other
    numbers run two runs: a reader checks the numbers by the digest."""
    elsewhere = FolderStore(store.root / "elsewhere")
    keep(store, _set())
    keep(elsewhere, _set(qe=0.09))

    here, _ = _grown(store, parameter_set="brighter")
    there, _ = _grown(elsewhere, parameter_set="brighter")

    assert here != there


def test_a_runs_manifest_answer_names_its_set_and_what_it_was_made_for(
    store: FolderStore,
) -> None:
    """A set made for another version of its model is run, and its answer
    says so beside the model's version (decision 0077)."""
    made = keep(store, _set(name="later") | {"made_for": 2})

    with _uploaded(store, parameter_set="later") as simulator:
        answer = run_manifest(simulator.catalogue, HOUSE)

    assert answer.parameter_set == SetRun(name="later", version=1, digest=made.digest, made_for=2)
    assert answer.models["crop"].version == 1
    published = run_manifest(PACKAGED, "tomgro_house").parameter_set
    assert published == SetRun(
        name="gnvman",
        version=1,
        digest=resolved(PUBLISHED_SETS[TOMGRO]).digest,
        made_for=1,
    )


def test_a_run_under_a_set_the_simulator_does_not_keep_is_refused(store: FolderStore) -> None:
    keep(store, _set())
    unknown = export_scenario_file(_house(parameter_set="brighter", parameter_set_version=2))

    with Simulator(runs=store) as simulator, pytest.raises(InvalidRequest) as refused:
        scenario_files.upload(simulator, unknown)
    assert refused.value.problems == (
        ("crop.parameter_set", "no set brighter v2 of reduced_tomgro is kept"),
    )
    with Simulator() as simulator, pytest.raises(InvalidRequest, match="does not keep"):
        scenario_files.upload(simulator, export_scenario_file(_house(parameter_set="brighter")))
    # A section that names a set it does not carry grows nothing, rather
    # than the published set's numbers.
    with pytest.raises(ValueError, match="not carried"):
        registration(_house(parameter_set="brighter")).area.rung(  # type: ignore[union-attr]
            _house(parameter_set="brighter")
        )


def test_a_scenarios_file_carries_its_set_and_runs_it_where_none_is_kept(
    store: FolderStore,
) -> None:
    """The file carries the set and each of its bases that is not published,
    its own first, so that a simulator keeping none runs the same run; one
    keeping the set's name and version with other numbers refuses it."""
    base = keep(store, _set())
    keep(store, _set(name="brighter_still", qe=0.12) | {"based_on": base.named.model_dump()})
    with _uploaded(store, parameter_set="brighter_still") as simulator:
        run_id = air_through_a_run(simulator, RunRequest(HOUSE))[1]
        text = scenario_files.download(simulator, HOUSE, with_recording=True).text
    carried = json.loads(text)["parameter_sets"]

    assert [each["name"] for each in carried] == ["brighter_still", "brighter"]
    with Simulator() as elsewhere:
        scenario_files.upload(elsewhere, text)
        assert air_through_a_run(elsewhere, RunRequest(HOUSE))[1] == run_id
    other = FolderStore(store.root / "other")
    keep(other, _set(qe=0.09))
    with Simulator(runs=other) as keeping, pytest.raises(Conflict, match="other numbers"):
        scenario_files.upload(keeping, text)
    published = json.loads(export_scenario_file(_house())) | {"parameter_sets": carried}
    with Simulator() as simulator, pytest.raises(InvalidRequest, match="parameter_sets"):
        scenario_files.upload(simulator, json.dumps(published))
    unread = json.loads(text) | {"parameter_sets": [carried[0] | {"made_for": 0}]}
    with Simulator() as simulator, pytest.raises(InvalidRequest) as refused:
        scenario_files.upload(simulator, json.dumps(unread))
    assert [field for field, _ in refused.value.problems] == ["parameter_sets[0].made_for"]


def test_a_set_is_kept_once_under_its_name_and_version(store: FolderStore) -> None:
    kept = keep(store, _set())

    assert keep(store, _set()) == kept
    assert json.loads(store.get(kept_name((TOMGRO, "brighter", 1))) or b"") == (
        kept.parameter_set.model_dump(mode="json")
    )
    with pytest.raises(Conflict, match="kept with other numbers"):
        keep(store, _set(qe=0.09))
    with pytest.raises(Conflict, match="kept with other numbers"):
        keep(store, _whole(name="gnvman", qe=QUANTUM_EFFICIENCY))
    assert keep(store, _set(name="brighter", version=2, qe=0.09)).digest != kept.digest
    with pytest.raises(InvalidRequest) as refused:
        keep(store, _set(name="dim", lai_max=-1.0))
    assert [field for field, _ in refused.value.problems] == ["parameters.lai_max"]


def test_a_crop_is_held_to_its_own_sets_bounds() -> None:
    """What no run reaches, and what a sample reads, are of the set the run
    grows: a canopy past the published set's most leaf area is one a set of
    a larger most grows."""
    leafier = resolved(read_parameter_set(_set(name="leafier", lai_max=6.0)))
    config = _house().model_copy(
        update={
            "crop": ReducedTomgroCrop(
                parameter_set="leafier",
                carried={
                    "files": (),
                    "values": leafier.values.model_dump(),
                    "digest": leafier.digest,
                },
            )
        }
    )
    registered = registration(config)
    assert registered.area is not None
    rung = registered.area.rung(config)
    assert isinstance(rung, TomgroRung)
    canopy = rung.planted().model_copy(update={"lai": 5.0})
    state = registered.state.model_validate(
        {"instances": [{"scope_id": "row_1", "state": canopy}], "lived": []}
    )

    assert rung.parameters.lai_max == 6.0
    assert registered.implausible(state, 1, config) == []
    assert registered.implausible(state, 1, _house()) == ["row_1's leaf area index is 5, past 4"]


def test_the_packaged_scenarios_run_only_their_models_published_sets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A calibration is a research result, cited by its name, version and
    digest, and never packaged (decision 0077)."""
    for scenario_id in PACKAGED.ids():
        crop = PACKAGED.configs[scenario_id].crop
        if isinstance(crop, ReducedTomgroCrop | VanthoorKatzinCrop):
            assert runs_published(crop), scenario_id
    document = json.loads((manifest_files.MANIFESTS_DIR / "tomgro_house.json").read_text())
    document["models"]["crop"]["parameters"]["parameter_set"] = "agc4_pretrial_2023"
    (tmp_path / "tomgro_house.json").write_text(json.dumps(document))
    monkeypatch.setattr(manifest_files, "MANIFESTS_DIR", tmp_path)

    with pytest.raises(InvalidManifest, match="published parameter set, gnvman"):
        load_manifest("tomgro_house")
