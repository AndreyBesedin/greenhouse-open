"""The revision recovery of example 05's `Steering` (P15.7): a revision
refused because the plan in force is newer is given once more, counted on
from the one read."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Final

from greenhouse_protocol.plan import Plan

EXAMPLES: Final = Path(__file__).resolve().parents[2] / "examples"

_spec = importlib.util.spec_from_file_location(
    "example_05_steering", EXAMPLES / "05_policy_in_its_own_process.py"
)
assert _spec is not None and _spec.loader is not None
REMOTE = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(REMOTE)


class _PortAhead:
    """A port whose plan in force is newer than the policy's own count."""

    def __init__(self, in_force: int) -> None:
        self.in_force = in_force
        self.submitted: list[int] = []

    def run(self) -> Any:
        return SimpleNamespace(run_id="run", epoch=0)

    def plan(self, plan_id: str) -> Any:
        return SimpleNamespace(plan=SimpleNamespace(revision=self.in_force))

    def submit(self, plan: Plan) -> Any:
        self.submitted.append(plan.revision)
        accepted = plan.revision > self.in_force
        if accepted:
            self.in_force = plan.revision
        return SimpleNamespace(accepted=accepted, revision=plan.revision)


def test_a_revision_refused_for_a_newer_plan_in_force_is_given_again_after_reading_it() -> None:
    port = _PortAhead(in_force=5)
    steering = REMOTE.Steering(port, "heating")

    receipt = steering.revise(())

    # Refused at 1, then the plan in force is read and the next one given.
    assert port.submitted == [1, 6]
    assert receipt.accepted
    assert steering.revision == 6
