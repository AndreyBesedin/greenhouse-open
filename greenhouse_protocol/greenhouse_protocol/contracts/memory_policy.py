"""An in-memory reference implementation of a policy's port (decision
0061): a run in memory, whose gateway is the in-memory one
(`greenhouse_protocol.contracts.memory_gateway`), whose producer's
observations, events and forecasts are delivered to it, and a port for
each principal that opens one, giving only what the allowlist lets
through. `check_policy_port` holds it to the contract, so a port of one's
own is developed against it.
"""

from collections.abc import Sequence
from datetime import datetime
from typing import Final

from greenhouse_protocol.actions import HEATING_SETPOINT_RANGE_C, ActionKind, ActionTargets
from greenhouse_protocol.authorisation import AuthorisationConfig
from greenhouse_protocol.budget import (
    ForecastProvider,
    ForecastUncertainty,
    InformationBasis,
    InformationBudget,
)
from greenhouse_protocol.context import (
    CapabilityContext,
    CropBasis,
    CropInstance,
    DeviceControl,
    Goal,
    ObservationSource,
    ObservedQuantity,
    SourceKind,
    TargetControl,
)
from greenhouse_protocol.contracts.consumer import (
    EventBatch,
    ForecastBatch,
    ObservationBatch,
    OutcomeBatch,
    RunDescriptor,
    delivered_at,
)
from greenhouse_protocol.contracts.gateway import PlanState, Receipt
from greenhouse_protocol.contracts.memory_gateway import InMemoryGateway
from greenhouse_protocol.contracts.policy import Delivered, readable_event, readable_forecast
from greenhouse_protocol.enums import ObservationType
from greenhouse_protocol.event import Event
from greenhouse_protocol.forecast import Forecast
from greenhouse_protocol.greenhouse import Plant
from greenhouse_protocol.observation import Observation
from greenhouse_protocol.plan import ActionKey, Plan, Principal

MINUTE_S: Final = 60.0
DAY_S: Final = 86_400.0

# What the memory run has, unless it is given otherwise: an air sensor and
# a weather station; a vent and a heater; the heating targets; a row of
# two plants.
SOURCES: Final = (
    ObservationSource(
        source_id="air_1",
        kind=SourceKind.SENSOR,
        quantities=(
            ObservedQuantity(observation_type=ObservationType.AIR_TEMPERATURE_C, every_s=MINUTE_S),
        ),
    ),
    ObservationSource(
        source_id="weather",
        kind=SourceKind.SENSOR,
        quantities=(
            ObservedQuantity(
                observation_type=ObservationType.OUTSIDE_AIR_TEMPERATURE_C, every_s=MINUTE_S
            ),
        ),
    ),
)
DEVICES: Final = (
    DeviceControl(device_id="heater", does=frozenset({"heats"}), auto=True),
    DeviceControl(device_id="vent_1", does=frozenset({"opens"})),
)
TARGETS: Final = tuple(
    TargetControl(
        target=target,
        unit="°C",
        low=HEATING_SETPOINT_RANGE_C[0],
        high=HEATING_SETPOINT_RANGE_C[1],
        observed_as=ObservationType.HEATING_TEMPERATURE_SETPOINT_C,
    )
    for target in ("heating_day", "heating_night")
)
CROPS: Final = (
    CropInstance(
        scope_id="row_1",
        scope_kind="row",
        grown_by=CropBasis.PLANT,
        cultivated_m2=1.0,
        floor_m2=2.0,
        plants=tuple(
            Plant(plant_id=plant_id, variety="memory", row=1, position_in_row=position)
            for position, plant_id in enumerate(("p30", "p31"), start=1)
        ),
        crop_actions=frozenset(
            {ActionKind.HARVEST, ActionKind.LOWER, ActionKind.REMOVE_LEAF, ActionKind.INSPECT}
        ),
    ),
)
# Tomorrow's outside air, hour by hour, as it was today: from the
# observations alone.
PERSISTENCE: Final = InformationBudget(
    budget_id="persistence",
    forecasts=(
        ForecastProvider(
            provider_id="persistence",
            version="1",
            basis=InformationBasis.OBSERVED,
            quantities=frozenset({ObservationType.OUTSIDE_AIR_TEMPERATURE_C}),
            issued_every_s=DAY_S,
            horizon_s=2 * DAY_S,
            uncertainty=ForecastUncertainty.NONE,
        ),
    ),
)


class InMemoryRun:
    """A run behind policies' ports, in memory: its gateway, its logs, what
    its policies may observe and act on, and the budget they are given. A
    record delivered to it joins its log when the clock reaches its
    delivery."""

    def __init__(
        self,
        authorisation: AuthorisationConfig,
        start: datetime,
        *,
        sources: Sequence[ObservationSource] = SOURCES,
        devices: Sequence[DeviceControl] = DEVICES,
        targets: Sequence[TargetControl] = TARGETS,
        crops: Sequence[CropInstance] = CROPS,
        goals: Sequence[Goal] = (),
        budget: InformationBudget = PERSISTENCE,
        greenhouse_id: str = "gh_memory",
        run_id: str = "run_memory",
    ) -> None:
        self.authorisation = authorisation
        self.budget = budget
        self._sources = tuple(sources)
        self._devices = tuple(devices)
        self._targets = tuple(targets)
        self._crops = tuple(crops)
        self._goals = tuple(goals)
        self.gateway = InMemoryGateway(
            authorisation,
            start,
            items=ActionTargets(
                devices=frozenset(device.device_id for device in self._devices),
                plants=frozenset(plant.plant_id for crop in self._crops for plant in crop.plants),
                targets=frozenset(target.target for target in self._targets),
            ),
            greenhouse_id=greenhouse_id,
            run_id=run_id,
        )
        self.observations: list[Observation] = []
        self.events: list[Event] = []
        self.forecasts: list[Forecast] = []
        self._pending: list[Delivered] = []

    def context(self, principal: Principal) -> CapabilityContext:
        run = self.gateway.run()
        return CapabilityContext(
            run_id=run.run_id,
            epoch=run.epoch,
            greenhouse_id=run.greenhouse_id,
            principal=principal,
            sources=self._sources,
            devices=self._devices,
            targets=self._targets,
            crops=self._crops,
            limits=self.gateway.limits(),
            grants=tuple(self.authorisation.grants_of(principal)),
            goals=self._goals,
        )

    def open(self, principal: Principal) -> InMemoryPolicyPort:
        return InMemoryPolicyPort(self, principal)

    def deliver(self, records: Sequence[Delivered]) -> None:
        self._pending += records
        self._release()

    def advance(self, to: datetime) -> None:
        self.gateway.advance(to)
        self._release()

    def authorise(self, config: AuthorisationConfig) -> None:
        self.authorisation = config
        self.gateway.authorise(config)

    def _release(self) -> None:
        """Each pending record delivered by the clock joins its log, in
        delivery order."""
        now = self.gateway.now
        due = sorted((r for r in self._pending if delivered_at(r) <= now), key=delivered_at)
        self._pending = [r for r in self._pending if delivered_at(r) > now]
        for record in due:
            match record:
                case Observation():
                    _append(self.observations, record)
                case Event():
                    _append(self.events, record)
                case Forecast():
                    _append(self.forecasts, record)


def _append[RecordT: (Observation, Event, Forecast)](log: list[RecordT], record: RecordT) -> None:
    if log and delivered_at(record) < delivered_at(log[-1]):
        raise ValueError(
            f"{record!r} was delivered before the last of its log: a log is in delivery order"
        )
    log.append(record)


def _page[RecordT](log: Sequence[RecordT], after: int, limit: int | None) -> tuple[RecordT, ...]:
    return tuple(log[after:] if limit is None else log[after : after + limit])


class InMemoryPolicyPort:
    """A port on an in-memory run, for one principal: see the module."""

    def __init__(self, run: InMemoryRun, principal: Principal) -> None:
        self._run = run
        self.principal = principal

    # The contract.

    def run(self) -> RunDescriptor:
        return self._run.gateway.run()

    def context(self) -> CapabilityContext:
        return self._run.context(self.principal)

    def budget(self) -> InformationBudget:
        return self._run.budget

    def observations(self, after: int = 0, limit: int | None = None) -> ObservationBatch:
        observed = self.context().observed_types()
        log = [o for o in self._run.observations if o.observation_type in observed]
        chosen = _page(log, after, limit)
        run = self.run()
        return ObservationBatch(
            run_id=run.run_id,
            epoch=run.epoch,
            after=after,
            next=after + len(chosen),
            simulated_now=run.clock.simulated_now,
            has_more=after + len(chosen) < len(log),
            observations=chosen,
        )

    def events(self, after: int = 0, limit: int | None = None) -> EventBatch:
        log = [readable_event(event) for event in self._run.events]
        chosen = _page(log, after, limit)
        run = self.run()
        return EventBatch(
            run_id=run.run_id,
            epoch=run.epoch,
            after=after,
            next=after + len(chosen),
            simulated_now=run.clock.simulated_now,
            has_more=after + len(chosen) < len(log),
            events=chosen,
        )

    def outcomes(self, after: int = 0, limit: int | None = None) -> OutcomeBatch:
        log = [o for o in self._run.gateway.outcomes().outcomes if self._owns(o.plan_id)]
        chosen = _page(log, after, limit)
        run = self.run()
        return OutcomeBatch(
            run_id=run.run_id,
            epoch=run.epoch,
            after=after,
            next=after + len(chosen),
            simulated_now=run.clock.simulated_now,
            has_more=after + len(chosen) < len(log),
            outcomes=chosen,
        )

    def forecasts(self, after: int = 0, limit: int | None = None) -> ForecastBatch:
        log = [f for f in self._run.forecasts if readable_forecast(f, self._run.budget)]
        chosen = _page(log, after, limit)
        run = self.run()
        return ForecastBatch(
            run_id=run.run_id,
            epoch=run.epoch,
            after=after,
            next=after + len(chosen),
            simulated_now=run.clock.simulated_now,
            has_more=after + len(chosen) < len(log),
            forecasts=chosen,
        )

    def plan(self, plan_id: str) -> PlanState | None:
        return self._run.gateway.plan(plan_id) if self._owns(plan_id) else None

    def submit(self, plan: Plan) -> Receipt:
        return self._run.gateway.submit(plan, by=self.principal)

    def cancel_plan(self, plan_id: str, *, revision: int, epoch: int) -> Receipt:
        return self._run.gateway.cancel_plan(
            plan_id, revision=revision, epoch=epoch, by=self.principal
        )

    def cancel(self, keys: Sequence[ActionKey]) -> Receipt:
        return self._run.gateway.cancel(keys, by=self.principal)

    # What a test moves its run with.

    def advance(self, to: datetime) -> None:
        self._run.advance(to)

    def deliver(self, records: Sequence[Delivered]) -> None:
        self._run.deliver(records)

    def open(self, principal: Principal) -> InMemoryPolicyPort:
        return self._run.open(principal)

    def _owns(self, plan_id: str) -> bool:
        try:
            return self._run.gateway.plan(plan_id).owner == self.principal
        except KeyError:
            return False
