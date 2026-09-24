"""Pluggable execution of already-validated actions against the world.

The simulation executes actions, but how it does so is replaceable
independently of who decided the action. `ActionExecutor` is that swap
point. `SimulatedOperatorExecutor` is the only implementation so far: it
executes instantaneously and completely (waters the exact requested amount,
harvests every ripe fruit in one pass). A future simulated robot (partial
completion, delays, failure rates) or a real executor (task creation, a
robot or climate controller) implements the same protocol, and nothing that
proposes actions has to change to add one.
"""

from datetime import datetime
from typing import Protocol

from greenhouse_protocol.action import RequestedAction
from greenhouse_protocol.enums import ActionExecutorType
from greenhouse_protocol.event import Event

from greenhouse_sim.actions import apply_action
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.world import GreenhouseWorld


class ActionExecutor(Protocol):
    def apply(
        self,
        world: GreenhouseWorld,
        action: RequestedAction,
        config: ScenarioConfig,
        *,
        day: int,
        timestamp: datetime,
    ) -> tuple[GreenhouseWorld, Event]: ...


class SimulatedOperatorExecutor:
    """Executes an accepted action instantaneously and completely."""

    def apply(
        self,
        world: GreenhouseWorld,
        action: RequestedAction,
        config: ScenarioConfig,
        *,
        day: int,
        timestamp: datetime,
    ) -> tuple[GreenhouseWorld, Event]:
        return apply_action(world, action, config, day=day, timestamp=timestamp)


def executor_for(executor_type: ActionExecutorType) -> ActionExecutor:
    """The executor a simulation definition asked for.

    Which executors exist is the simulator's knowledge, not its caller's,
    so the mapping lives here rather than in whatever harness drives a run.
    """
    if executor_type == ActionExecutorType.SIMULATED_OPERATOR:
        return SimulatedOperatorExecutor()
    raise ValueError(f"unknown action executor type: {executor_type!r}")
