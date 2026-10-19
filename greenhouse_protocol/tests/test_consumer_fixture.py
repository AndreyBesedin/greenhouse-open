"""The recorded exchange a consumer is developed against
(`greenhouse_protocol.contracts.consumer`, "Fixtures").

The exchange is built here from the protocol's own records, so that it
depends on no producer, and written to `fixtures/consumer/exchange.json`:

    python greenhouse_protocol/tests/test_consumer_fixture.py --update

The tests hold the file to what this module builds, to the interface's
rules, and to what a client following the rules ends up storing.
"""

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from greenhouse_protocol.contracts.consumer import (
    CONSUMER_INTERFACE_VERSION,
    CONSUMER_PREFIX,
    FIRST_CURSOR,
    FIRST_EPOCH,
    EventBatch,
    ObservationBatch,
    RunClock,
    RunDescriptor,
    RunList,
    check_batch,
    check_polls,
    check_run,
    record_id,
)
from greenhouse_protocol.enums import EventSource, EventType, ObservationType, SourceType
from greenhouse_protocol.event import Event
from greenhouse_protocol.greenhouse import (
    GreenhouseDescription,
    GreenhouseLayout,
    build_grid_plants,
)
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.provenance import RecordSource

FIXTURE = Path(__file__).parent / "fixtures" / "consumer" / "exchange.json"

RUN_ID = "consumer_demo"
GREENHOUSE_ID = "consumer_demo"
RUN = f"{CONSUMER_PREFIX}/runs/{RUN_ID}"
STARTED_AT = datetime(2026, 3, 1, 0, 0, tzinfo=UTC)
# The run samples at local noon, and the client polls half a minute later,
# once the slowest sensor's reading of the day has been delivered.
SAMPLE_TIME = timedelta(hours=12)
AIR_LATENCY = timedelta(seconds=30)
LATE_BY = timedelta(days=1, seconds=5)
SOURCE = RecordSource(type=SourceType.SIMULATION, source_id=RUN_ID)
PLANTS = tuple(build_grid_plants(GREENHOUSE_ID, "tomato", rows=1, columns=2))
PLANT_1, PLANT_2 = (plant.plant_id for plant in PLANTS)
# A crop that grows a little each day, and ripens from day 2.
HEIGHTS_CM = {PLANT_1: (41.0, 43.5, 46.0), PLANT_2: (39.0, 41.0, 43.5)}
RIPE_COUNTS = {PLANT_1: (0, 1, 2), PLANT_2: (0, 0, 1)}
AIR_TEMPERATURES_C = (21.4, 22.1, 20.8)
LATE_HUMIDITY_PCT = 78.0
HARVESTED = {"fruit_count": 2, "mass_g": 150.0}
# One batch is cut short to show `has_more`.
SHORT_LIMIT = 2


def _day(day: int) -> datetime:
    return STARTED_AT + timedelta(days=day)


def _clock(day: int) -> RunClock:
    return RunClock(simulated_now=_day(day) + SAMPLE_TIME + AIR_LATENCY, day=day, playing=True)


def _run(epoch: int, day: int) -> RunDescriptor:
    return RunDescriptor(
        run_id=RUN_ID,
        epoch=epoch,
        greenhouse_id=GREENHOUSE_ID,
        scenario="demo",
        started_at=STARTED_AT,
        clock=_clock(day),
    )


def greenhouse() -> GreenhouseDescription:
    return GreenhouseDescription(
        greenhouse_id=GREENHOUSE_ID,
        name="Consumer demo",
        description="Two tomato plants, one air sensor, three days.",
        source_type=SourceType.SIMULATION,
        crop="tomato",
        layout=GreenhouseLayout(rows=1, columns=2),
        plants=PLANTS,
        created_at=STARTED_AT,
    )


def _observation(
    plant_id: str | None,
    taken: datetime,
    kind: ObservationType,
    value: float,
    *,
    sensor_id: str | None = None,
    delivered: datetime | None = None,
) -> Observation:
    subject = plant_id or sensor_id or GREENHOUSE_ID
    return Observation(
        observation_id=f"{subject}_{taken.strftime('%Y%m%dT%H%M%S')}_{kind.value}",
        greenhouse_id=GREENHOUSE_ID,
        plant_id=plant_id,
        timestamp=taken,
        observation_type=kind,
        value=value,
        source=SOURCE,
        sensor_id=sensor_id,
        delivered_at=delivered,
    )


def observations_delivered_on(day: int) -> list[Observation]:
    """What the run delivers on a day, in delivery order: the vision pass
    at noon, then on day 2 a humidity reading from the day before, then the
    air sensor's reading after its latency."""
    noon = _day(day) + SAMPLE_TIME
    index = day - 1
    delivered = [
        _observation(plant, noon, ObservationType.VISIBLE_HEIGHT_CM, HEIGHTS_CM[plant][index])
        for plant in (PLANT_1, PLANT_2)
    ]
    if day >= 2:
        delivered += [
            _observation(plant, noon, ObservationType.RIPE_FRUIT_COUNT, RIPE_COUNTS[plant][index])
            for plant in (PLANT_1, PLANT_2)
        ]
    if day == 2:
        taken = _day(1) + SAMPLE_TIME
        delivered.append(
            _observation(
                None,
                taken,
                ObservationType.RELATIVE_HUMIDITY_PCT,
                LATE_HUMIDITY_PCT,
                sensor_id="rh_1",
                delivered=taken + LATE_BY,
            )
        )
    delivered.append(
        _observation(
            None,
            noon,
            ObservationType.AIR_TEMPERATURE_C,
            AIR_TEMPERATURES_C[index],
            sensor_id="air_1",
            delivered=noon + AIR_LATENCY,
        )
    )
    return delivered


def events_delivered_on(day: int) -> list[Event]:
    noon = _day(day) + SAMPLE_TIME
    if day == 2:
        return [
            Event(
                event_id=f"{GREENHOUSE_ID}_{noon.strftime('%Y%m%dT%H%M%S')}_watering",
                greenhouse_id=GREENHOUSE_ID,
                plant_id=None,
                timestamp=noon,
                event_type=EventType.WATERING,
                source=EventSource.CONTROL_SYSTEM,
                parameters={"volume_ml": 500.0},
            )
        ]
    if day == 3:
        return [
            Event(
                event_id=f"{PLANT_1}_{noon.strftime('%Y%m%dT%H%M%S')}_harvest",
                greenhouse_id=GREENHOUSE_ID,
                plant_id=PLANT_1,
                timestamp=noon,
                event_type=EventType.HARVEST,
                source=EventSource.SIMULATION,
                parameters=dict(HARVESTED),
            )
        ]
    return []


class _Producer:
    """A conforming producer over the records above, one epoch at a time,
    whose logs grow as the day advances."""

    def __init__(self, epoch: int) -> None:
        self.epoch = epoch
        self.day = 0
        self.observations: list[Observation] = []
        self.events: list[Event] = []

    def advance_to(self, day: int) -> None:
        while self.day < day:
            self.day += 1
            self.observations += observations_delivered_on(self.day)
            self.events += events_delivered_on(self.day)

    def run(self) -> RunDescriptor:
        return _run(self.epoch, self.day)

    def observation_batch(self, after: int, limit: int | None = None) -> ObservationBatch:
        records, has_more = self._slice(self.observations, after, limit)
        return ObservationBatch(
            run_id=RUN_ID,
            epoch=self.epoch,
            after=after,
            next=after + len(records),
            simulated_now=self.run().clock.simulated_now,
            has_more=has_more,
            observations=tuple(records),
        )

    def event_batch(self, after: int, limit: int | None = None) -> EventBatch:
        records, has_more = self._slice(self.events, after, limit)
        return EventBatch(
            run_id=RUN_ID,
            epoch=self.epoch,
            after=after,
            next=after + len(records),
            simulated_now=self.run().clock.simulated_now,
            has_more=has_more,
            events=tuple(records),
        )

    @staticmethod
    def _slice[T](log: list[T], after: int, limit: int | None) -> tuple[list[T], bool]:
        rest = log[after:]
        if limit is not None and len(rest) > limit:
            return rest[:limit], True
        return rest, False


def _step(
    path: str, body: Any, query: dict[str, int] | None = None, status: int = 200
) -> dict[str, Any]:
    step: dict[str, Any] = {"method": "GET", "path": path, "query": query or {}, "status": status}
    step["body"] = body.model_dump(mode="json") if hasattr(body, "model_dump") else body
    return step


def build_exchange() -> dict[str, Any]:
    """The exchange: a client following a run through three days, a cut
    batch, a repoll, a stale cursor, and the run starting over."""
    first = _Producer(FIRST_EPOCH)
    first.advance_to(1)
    # In the order a client makes them: it discovers the run and reads the
    # greenhouse once, then each day reads the clock and drains both logs.
    steps = [
        _step(f"{CONSUMER_PREFIX}/runs", RunList(runs=(first.run(),))),
        _step(f"{RUN}/greenhouse", greenhouse()),
        _step(f"{CONSUMER_PREFIX}/runs/unknown", {"detail": "no run 'unknown'"}, status=404),
        _step(RUN, first.run()),
        _step(
            f"{RUN}/observations", first.observation_batch(FIRST_CURSOR), {"after": FIRST_CURSOR}
        ),
        _step(f"{RUN}/events", first.event_batch(FIRST_CURSOR), {"after": FIRST_CURSOR}),
        # A repoll at the same cursor and clock answers the same records.
        _step(
            f"{RUN}/observations", first.observation_batch(FIRST_CURSOR), {"after": FIRST_CURSOR}
        ),
    ]
    after = first.observation_batch(FIRST_CURSOR).next
    first.advance_to(2)
    cut = first.observation_batch(after, SHORT_LIMIT)
    steps += [
        _step(RUN, first.run()),
        _step(f"{RUN}/observations", cut, {"after": after, "limit": SHORT_LIMIT}),
        _step(f"{RUN}/observations", first.observation_batch(cut.next), {"after": cut.next}),
        _step(f"{RUN}/events", first.event_batch(FIRST_CURSOR), {"after": FIRST_CURSOR}),
    ]
    after = first.observation_batch(cut.next).next
    events_after = first.event_batch(FIRST_CURSOR).next
    first.advance_to(3)
    steps += [
        _step(RUN, first.run()),
        _step(f"{RUN}/observations", first.observation_batch(after), {"after": after}),
        _step(f"{RUN}/events", first.event_batch(events_after), {"after": events_after}),
    ]
    after = first.observation_batch(after).next
    steps.append(_step(f"{RUN}/observations", first.observation_batch(after), {"after": after}))
    # The run starts over: a new epoch, the same days again. The client's
    # cursor is stale and answered empty; it sees the epoch and starts from 0.
    second = _Producer(FIRST_EPOCH + 1)
    second.advance_to(1)
    steps += [
        _step(RUN, second.run()),
        _step(f"{RUN}/observations", second.observation_batch(after), {"after": after}),
        _step(
            f"{RUN}/observations", second.observation_batch(FIRST_CURSOR), {"after": FIRST_CURSOR}
        ),
        _step(f"{RUN}/events", second.event_batch(FIRST_CURSOR), {"after": FIRST_CURSOR}),
    ]
    return {"interface_version": CONSUMER_INTERFACE_VERSION, "steps": steps}


def _rendered(exchange: dict[str, Any]) -> str:
    return json.dumps(exchange, indent=2) + "\n"


def _batches(exchange: dict[str, Any], kind: str) -> list[ObservationBatch | EventBatch]:
    model: type[ObservationBatch] | type[EventBatch]
    model = ObservationBatch if kind == "observations" else EventBatch
    return [
        model.model_validate(step["body"])
        for step in exchange["steps"]
        if step["path"].endswith(f"/{kind}") and step["status"] == 200
    ]


def test_the_fixture_is_what_this_module_builds() -> None:
    assert FIXTURE.read_text() == _rendered(build_exchange()), (
        "the exchange changed: python greenhouse_protocol/tests/test_consumer_fixture.py --update"
    )


def test_every_answer_in_the_fixture_is_its_route_s_payload() -> None:
    exchange = json.loads(FIXTURE.read_text())
    assert exchange["interface_version"] == CONSUMER_INTERFACE_VERSION
    for step in exchange["steps"]:
        path, body = step["path"], step["body"]
        if step["status"] != 200:
            assert "detail" in body
        elif path == f"{CONSUMER_PREFIX}/runs":
            RunList.model_validate(body)
        elif path == RUN:
            assert check_run(RunDescriptor.model_validate(body)) == []
        elif path.endswith("/greenhouse"):
            GreenhouseDescription.model_validate(body)
        elif path.endswith("/observations"):
            assert check_batch(ObservationBatch.model_validate(body)) == []
        elif path.endswith("/events"):
            assert check_batch(EventBatch.model_validate(body)) == []
        else:
            raise AssertionError(f"a step the interface does not describe: {path}")


def test_the_fixture_s_polls_follow_the_rules_together() -> None:
    exchange = json.loads(FIXTURE.read_text())

    assert check_polls(_batches(exchange, "observations")) == []
    assert check_polls(_batches(exchange, "events")) == []


def test_the_fixture_shows_what_a_client_must_handle() -> None:
    exchange = json.loads(FIXTURE.read_text())
    observations = _batches(exchange, "observations")

    assert any(batch.has_more for batch in observations), "a cut batch"
    late = [
        record
        for batch in observations
        for record in batch.records
        if isinstance(record, Observation)
        and record.delivered_at is not None
        and record.delivered_at - record.timestamp >= timedelta(days=1)
    ]
    assert late, "a reading delivered a day after it was taken"
    assert {batch.epoch for batch in observations} == {FIRST_EPOCH, FIRST_EPOCH + 1}, "a restart"
    assert any(
        batch.epoch > FIRST_EPOCH and batch.after > 0 and not batch.records
        for batch in observations
    ), "a stale cursor answered empty in the new epoch"
    events = _batches(exchange, "events")
    assert any(
        isinstance(record, Event) and record.event_type == EventType.HARVEST
        for batch in events
        for record in batch.records
    ), "a harvest"


def test_a_client_following_the_rules_stores_each_record_once_per_epoch() -> None:
    """The reference client: keep a cursor per log, start over on a new
    epoch, store by (epoch, id), and never store anything twice."""
    exchange = json.loads(FIXTURE.read_text())
    stored: dict[tuple[int, str], set[str]] = {}
    cursor: dict[str, int] = {}
    epoch = FIRST_EPOCH
    for step in exchange["steps"]:
        for kind, model in (("observations", ObservationBatch), ("events", EventBatch)):
            if step["path"].endswith(f"/{kind}") and step["status"] == 200:
                batch = model.model_validate(step["body"])
                if batch.epoch != epoch:
                    epoch, cursor = batch.epoch, {}
                if batch.after != cursor.get(kind, FIRST_CURSOR):
                    # A poll the client would not have made from its cursor:
                    # the fixture's repoll and stale cursor; it stores nothing.
                    continue
                kept = stored.setdefault((epoch, kind), set())
                for record in batch.records:
                    assert record_id(record) not in kept
                    kept.add(record_id(record))
                cursor[kind] = batch.next

    assert len(stored[(FIRST_EPOCH, "observations")]) == 14
    assert len(stored[(FIRST_EPOCH, "events")]) == 2
    assert len(stored[(FIRST_EPOCH + 1, "observations")]) == 3
    assert (FIRST_EPOCH + 1, "events") not in stored or stored[(FIRST_EPOCH + 1, "events")] == set()


if __name__ == "__main__":
    if sys.argv[1:] != ["--update"]:
        raise SystemExit(f"usage: {sys.argv[0]} --update")
    FIXTURE.write_text(_rendered(build_exchange()))
    print(f"wrote {FIXTURE}")
