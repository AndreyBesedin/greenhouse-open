"""The canonical contract, checked against every producer that exists.

The simulator and the recorded WUR adapter describe observations without
importing each other. These tests run the same checks over both: one
contract, two independent implementations of it, neither privileged.

They also check the checks. A conformance suite that cannot fail is worth
nothing, so each rule is exercised against a record that breaks it.
"""

from datetime import UTC, datetime, timedelta

from greenhouse_adapters.wur.agc4_challenge_2024.compartments import compartment
from greenhouse_adapters.wur.agc4_challenge_2024.timeseries import parse_timeseries
from greenhouse_protocol.action import WaterPlantAction
from greenhouse_protocol.contracts.conformance import (
    check_events,
    check_frames,
    check_media,
    check_observations,
)
from greenhouse_protocol.enums import (
    CaptureModality,
    EventSource,
    EventType,
    SourceType,
)
from greenhouse_protocol.event import Event
from greenhouse_protocol.media import CameraFrame, CameraPose, MediaCapture
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.provenance import RecordSource
from greenhouse_protocol.sensor import CameraIntrinsics
from greenhouse_sim.engine import SimulationEngine
from greenhouse_sim.scenarios import SCENARIO_REGISTRY
from greenhouse_sim.services import sensors

CONFIG = SCENARIO_REGISTRY["tomato_compartment"]
PLANT_IDS = ["tomato_compartment_plant_001", "tomato_compartment_plant_002"]
START = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)

# The same slice of a WUR compartment export the adapter's own tests use:
# the time column, mapped channels, a gap, and the DST changeover.
WUR_CSV = """\
time,compartment/air_temperature,compartment/relative_humidity,compartment/heating_temperature_setpoint
2024-10-27 02:55:00+02:00,19.5,81.0,18.0
2024-10-27 02:00:00+01:00,19.4,,18.0
2024-10-27 02:05:00+01:00,,80.5,18.5
"""


def _simulated() -> tuple[list[Observation], list[Event]]:
    engine = SimulationEngine(CONFIG)
    world = engine.initialize(PLANT_IDS, greenhouse_id="tomato_compartment")
    observations: list[Observation] = []
    events: list[Event] = []

    for day in range(1, 8):
        timestamp = START + timedelta(days=day - 1)
        step = engine.advance(world, day=day, timestamp=timestamp, simulation_id="sim_conformance")
        execution = engine.apply_actions(
            step.world,
            [WaterPlantAction(plant_id=PLANT_IDS[0], amount_ml=250.0)],
            day=day,
            timestamp=timestamp,
        )
        world = execution.world
        observations.extend(step.observations)
        events.extend(execution.events)

    return observations, events


def test_the_simulator_conforms_to_the_canonical_contract() -> None:
    observations, events = _simulated()

    assert observations and events
    assert check_observations(observations) == []
    assert check_events(events) == []


def test_the_recorded_adapter_conforms_to_the_same_contract() -> None:
    """Including across the daylight-saving changeover, where a wall-clock
    reading would be ambiguous and two records could collide."""
    observations = list(parse_timeseries(WUR_CSV.splitlines(), compartment("3.06")))

    assert observations
    assert check_observations(observations) == []


def test_both_producers_pass_the_same_checks_on_one_combined_batch() -> None:
    """Records from different producers coexist: a consumer reading both
    sees one stream, so their identities must not collide either."""
    simulated, _ = _simulated()
    recorded = list(parse_timeseries(WUR_CSV.splitlines(), compartment("3.06")))

    assert check_observations([*simulated, *recorded]) == []


def _observation(**overrides: object) -> Observation:
    fields: dict[str, object] = {
        "observation_id": "obs_1",
        "greenhouse_id": "tomato_compartment",
        "plant_id": None,
        "timestamp": START,
        "observation_type": "air_temperature_c",
        "value": 21.0,
        "source": RecordSource(type=SourceType.SIMULATION, source_id="sim"),
    }
    fields.update(overrides)
    return Observation.model_validate(fields)


def test_a_wall_clock_timestamp_is_refused() -> None:
    naive = _observation(timestamp=datetime(2026, 7, 1, 12, 0))

    violations = check_observations([naive])

    assert len(violations) == 1
    assert "no timezone" in violations[0]


def test_two_records_sharing_an_identity_are_refused() -> None:
    first = _observation()
    second = _observation(timestamp=START + timedelta(hours=1))

    violations = check_observations([first, second])

    assert any("two different instants" in v for v in violations)


def test_a_placeholder_reading_is_refused() -> None:
    """A gap is an absent record, not a NaN in a value field."""
    violations = check_observations([_observation(value=float("nan"))])

    assert len(violations) == 1
    assert "non-finite" in violations[0]


def test_an_unscoped_record_is_refused() -> None:
    violations = check_observations([_observation(greenhouse_id="  ")])

    assert any("names no greenhouse" in v for v in violations)


def test_an_impossible_event_confidence_is_refused() -> None:
    event = Event(
        event_id="evt_1",
        greenhouse_id="tomato_compartment",
        plant_id=None,
        timestamp=START,
        event_type=EventType.HARVEST,
        source=EventSource.RULE_BASED_POLICY,
        confidence=1.5,
    )

    violations = check_events([event])

    assert any("outside 0..1" in v for v in violations)


def test_a_capture_without_bytes_behind_it_is_refused() -> None:
    capture = MediaCapture(
        capture_id="cap_1",
        greenhouse_id="tomato_compartment",
        sensor_id="cam_1",
        timestamp=START,
        modality=CaptureModality.RGB,
        artifact_uri="   ",
        source=RecordSource(type=SourceType.IMPORTED_DATA, source_id="wur"),
    )

    violations = check_media([capture])

    assert any("empty artifact reference" in v for v in violations)


def _frame(**overrides: object) -> CameraFrame:
    defaults: dict[str, object] = dict(
        frame_id="frame_1",
        greenhouse_id="climate_box",
        sensor_id="cam_1",
        timestamp=START,
        pose=CameraPose(x_m=0.6, y_m=3.2, z_m=2.2, qw=1.0, qx=0.0, qy=0.0, qz=0.0),
        intrinsics=CameraIntrinsics(width=640, height=480, fx=457.0, fy=457.0, ppx=320, ppy=240),
        modalities=(CaptureModality.RGB, CaptureModality.DEPTH),
        source=RecordSource(type=SourceType.SIMULATION, source_id="run"),
    )
    defaults.update(overrides)
    return CameraFrame(**defaults)


def test_the_simulators_camera_frames_conform() -> None:
    log = sensors.observations("climate_box", until_s=300)

    assert len(log.frames) == 6
    assert check_frames(log.frames) == []


def test_a_frame_must_be_unambiguous_named_and_delivered_after_it_was_taken() -> None:
    naive = _frame(frame_id="naive", timestamp=START.replace(tzinfo=None))
    nameless = _frame(frame_id="nameless", sensor_id=" ", timestamp=START + timedelta(minutes=1))
    early = _frame(
        frame_id="early",
        timestamp=START + timedelta(minutes=2),
        delivered_at=START + timedelta(minutes=1),
    )

    violations = check_frames([naive, nameless, early, _frame(frame_id="naive")])

    assert any("no timezone" in v for v in violations)
    assert any("names no camera" in v for v in violations)
    assert any("delivered" in v and "before it was taken" in v for v in violations)
    assert any("appear more than once" in v for v in violations)
