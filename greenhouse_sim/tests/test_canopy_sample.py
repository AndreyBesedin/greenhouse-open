"""A measurement model of a crop grown by area (P14.9, decision 0062): a
sample of each scope's canopy, chosen by the manifest as a model of the crop
walk's part, named and versioned in a run's identity. Its readings name
their scope and no plant, and carry the sample's errors, the model's state
staying the evaluation's truth."""

import json
import sys
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import pytest
from greenhouse_protocol.context import CapabilityContext, CropBasis, SourceKind
from greenhouse_protocol.contracts.gateway import GatewayLimits
from greenhouse_protocol.enums import ObservationType, SourceType
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.plan import Principal, PrincipalKind
from greenhouse_protocol.provenance import RecordSource
from pydantic import ValidationError

from greenhouse_sim.domain.parts import Part
from greenhouse_sim.evaluation.observation_accuracy import observation_accuracy
from greenhouse_sim.ground_truth import ground_truth
from greenhouse_sim.scenarios.catalogue import Catalogue
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.scenarios.crop_parameters import CanopySample
from greenhouse_sim.scenarios.manifest_files import MANIFESTS_DIR, scenario_from_manifest
from greenhouse_sim.scenarios.registry import models_run
from greenhouse_sim.services.crop import of_plants, scenario_crop
from greenhouse_sim.services.crop_log import crop_records
from greenhouse_sim.services.fields import air_through_a_run
from greenhouse_sim.services.gateway import LOCAL_AUTHORISATION, LOCAL_OPERATOR
from greenhouse_sim.services.playback import Playback, PlaybackCommand
from greenhouse_sim.services.policy_context import run_context
from greenhouse_sim.services.run_store import OBSERVATIONS, _observation_row
from greenhouse_sim.services.runs import RunRequest
from greenhouse_sim.services.scenarios import scenario
from greenhouse_sim.services.simulator import Simulator
from greenhouse_sim.units import DAY_S

sys.path.insert(0, str(Path(__file__).parent))

from short_runs import cut

SCENARIO: Final = "tomgro_sampled"
POLICY: Final = Principal(kind=PrincipalKind.POLICY, id="policy")
RUN: Final = RunRequest(SCENARIO)
START: Final = datetime(2026, 1, 1, tzinfo=UTC)
ROWS: Final = ("row_1", "row_2")
SAMPLED: Final = (
    ObservationType.LEAF_AREA_INDEX,
    ObservationType.ABOVE_GROUND_DRY_WEIGHT_G_M2,
    ObservationType.FRUIT_DRY_WEIGHT_G_M2,
    ObservationType.MATURE_FRUIT_DRY_WEIGHT_G_M2,
)


def _config(greenhouse_id: str = SCENARIO, **sample: Any) -> ScenarioConfig:
    """The climate box, its rows growing Reduced-State TOMGRO, sampled."""
    return cut(
        "climate_box",
        days=5,
        sensors=("temperature_front",),
        greenhouse_id=greenhouse_id,
        crop_model="reduced_tomgro",
        crop={"kind": "reduced_tomgro"},
        crop_walk={"kind": "canopy_sample", "every_days": 2} | sample,
    )


def _simulator(*configs: ScenarioConfig) -> Simulator:
    simulator = Simulator(Catalogue())
    for config in configs:
        simulator.catalogue.register(config)
    return simulator


@pytest.fixture(scope="module")
def perfect() -> Iterator[Simulator]:
    with _simulator(_config(noise_pct=0.0)) as simulator:
        yield simulator


def _context(config: ScenarioConfig) -> CapabilityContext:
    return run_context(
        config,
        run_id="a_run",
        epoch=0,
        principal=LOCAL_OPERATOR,
        authorisation=LOCAL_AUTHORISATION,
        limits=GatewayLimits(max_actions=10, max_occurrences=100),
        every_s=300.0,
    )


def _walked(config: ScenarioConfig) -> ScenarioConfig:
    """`config` measured by the part's default, the walk."""
    return config.model_copy(update={"crop_walk": ScenarioConfig.model_fields["crop_walk"].default})


def _records(simulator: Simulator, run: RunRequest, day: int) -> list[Observation]:
    observations, events = crop_records(simulator, run, day, START, "a_run")
    assert events == []
    return observations


def test_it_reads_each_scope_on_the_days_it_samples_naming_its_scope_and_no_plant(
    perfect: Simulator,
) -> None:
    assert _records(perfect, RUN, 1) == _records(perfect, RUN, 3) == []

    taken = _records(perfect, RUN, 2)

    assert [(o.scope_id, o.observation_type) for o in taken] == [
        (row, kind) for row in ROWS for kind in SAMPLED
    ]
    assert {o.plant_id for o in taken} == {None}
    crop = scenario_crop(perfect, RUN)
    assert not of_plants(crop)
    # The crop as it stands at the walk's moment, read with no error, per m²
    # of floor, which is the model's own basis.
    canopy = {instance.scope_id: instance.state for instance in crop.instances_on(2)}
    by_scope = {(o.scope_id, o.observation_type): o.value for o in taken}
    for row in ROWS:
        assert by_scope[row, ObservationType.LEAF_AREA_INDEX] == round(canopy[row].lai, 3)
        assert by_scope[row, ObservationType.ABOVE_GROUND_DRY_WEIGHT_G_M2] == round(
            canopy[row].w, 3
        )


def test_its_errors_are_its_own_parameters_and_are_seeded() -> None:
    noisy, biased = (
        _config("noisy", noise_pct=20.0),
        _config("biased", noise_pct=0.0, bias_pct=50.0),
    )
    clean = _config("clean", noise_pct=0.0)
    with _simulator(noisy, biased, clean) as simulator:
        read = {
            config.greenhouse_id: {
                (o.scope_id, o.observation_type): o.value
                for o in _records(simulator, RunRequest(config.greenhouse_id), 4)
            }
            for config in (noisy, biased, clean)
        }
        again = _records(simulator, RunRequest("noisy"), 4)

    leaves = "row_1", ObservationType.LEAF_AREA_INDEX
    assert read["clean"][leaves] > 0.0
    assert read["biased"][leaves] == pytest.approx(1.5 * read["clean"][leaves], abs=2e-3)
    assert read["noisy"][leaves] != read["clean"][leaves]
    # Each scope draws its own error: rows that grow alike read apart.
    assert read["noisy"][leaves] != read["noisy"]["row_2", ObservationType.LEAF_AREA_INDEX]
    assert {(o.scope_id, o.observation_type): o.value for o in again} == read["noisy"]


def test_a_walk_finds_nothing_to_measure_in_a_crop_grown_by_area() -> None:
    config = _walked(_config("walked"))
    with _simulator(config) as simulator:
        assert _records(simulator, RunRequest("walked"), 2) == []
    assert not [s for s in _context(config).sources if s.kind == SourceKind.MEASUREMENT]


def test_it_is_refused_for_a_crop_of_plants() -> None:
    with pytest.raises(ValidationError, match="canopy_sample measures a crop grown by area"):
        cut("climate_box", crop_walk={"kind": "canopy_sample"})


def test_it_is_a_model_a_manifest_chooses_and_a_run_is_named_by() -> None:
    document = json.loads((MANIFESTS_DIR / "tomgro_house.json").read_text())
    document["models"]["crop_walk"] = {"model": "canopy_sample", "parameters": {"every_days": 3}}

    read = scenario_from_manifest("tomgro_house", document)

    assert read.crop_walk == CanopySample(every_days=3)
    assert models_run(read)[Part.CROP_WALK].model_dump() == {"model": "canopy_sample", "version": 1}
    # A perfect instrument is asked for: the model's default has errors.
    assert CanopySample().noise_pct > 0

    one, other = _config("one", noise_pct=0.0), _config("one", noise_pct=1.0)
    with _simulator(one) as simulator:
        _, first = air_through_a_run(simulator, RunRequest("one"))
    with _simulator(other) as simulator:
        _, second = air_through_a_run(simulator, RunRequest("one"))
    with _simulator(_walked(one)) as simulator:
        _, by_a_walk = air_through_a_run(simulator, RunRequest("one"))
    assert len({first, second, by_a_walk}) == 3


def test_its_readings_are_scored_against_the_scopes_truth() -> None:
    biased = _config("scored", noise_pct=0.0, bias_pct=10.0)
    run = RunRequest("scored")
    with _simulator(biased) as simulator:
        truth = ground_truth(simulator, run, until_s=biased.duration_days * DAY_S)
        taken = [
            observation
            for day in range(biased.duration_days)
            for observation in crop_records(simulator, run, day, _start(simulator), truth.run_id)[0]
        ]
    report = observation_accuracy(taken, truth)

    # Every reading of days 0, 2 and 4, of two scopes, of four quantities.
    assert report.readings == len(taken) == 3 * 2 * 4
    leaves = report.for_type(ObservationType.LEAF_AREA_INDEX)
    assert leaves.mean_absolute_error == pytest.approx(0.1 * leaves.mean_true_value, abs=1e-3)


def _start(simulator: Simulator) -> datetime:
    return scenario(simulator.catalogue, "scored").run_start()


def test_a_policy_is_told_each_sample_by_its_scope_and_that_the_crop_is_grown_by_area() -> None:
    context = _context(_config(noise_pct=0.0))

    samples = {s.scope_id: s for s in context.sources if s.kind == SourceKind.MEASUREMENT}
    assert set(samples) == set(ROWS)
    every_two_days = 2 * DAY_S
    for source in samples.values():
        assert {q.observation_type: q.every_s for q in source.quantities} == dict.fromkeys(
            SAMPLED, every_two_days
        )
    assert {crop.grown_by for crop in context.crops} == {CropBasis.AREA}
    assert set(SAMPLED) <= context.observed_types()


class _Clock:
    now = 0.0

    def __call__(self) -> float:
        return self.now


def test_a_playback_delivers_its_samples_to_a_policy_by_their_scope() -> None:
    clock = _Clock()
    with _simulator(_config(noise_pct=0.0)) as simulator:
        played = Playback(simulator, SCENARIO, seconds_per_day=24.0, clock=clock)
        context = played.context(POLICY)
        assert played.work_day(0)
        played.command(PlaybackCommand.PLAY)
        clock.now = 24.0
        readings = played.records_after(0, 10**6).records
        played.stop()

    samples = [reading for reading in readings if reading.scope_id is not None]
    assert {(reading.scope_id, reading.observation_type) for reading in samples} == {
        (row, kind) for row in ROWS for kind in SAMPLED
    }
    assert {reading.scope_id for reading in samples} == {
        source.scope_id for source in context.sources if source.kind == SourceKind.MEASUREMENT
    }


def _a_reading(**changes: Any) -> Observation:
    return Observation(
        observation_id="sample",
        greenhouse_id=SCENARIO,
        plant_id=None,
        scope_id="row_1",
        timestamp=START,
        observation_type=ObservationType.LEAF_AREA_INDEX,
        value=1.25,
        source=RecordSource(type=SourceType.SIMULATION, source_id="a_run"),
    ).model_copy(update=changes)


def test_the_run_store_keeps_its_scope_and_reads_a_segment_written_before_it() -> None:
    reading = _a_reading()
    assert OBSERVATIONS.decode(OBSERVATIONS.encode([reading])) == [reading]

    earlier = replace(
        OBSERVATIONS,
        columns=OBSERVATIONS.columns[:-1],
        row=lambda observation: _observation_row(observation)[:-1],
    )
    assert OBSERVATIONS.decode(earlier.encode([reading])) == [_a_reading(scope_id=None)]
