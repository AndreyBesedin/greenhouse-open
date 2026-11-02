"""A policy in a process of its own, steering a run over the network.

    python examples/05_policy_in_its_own_process.py

The same naive heating rule as example 03, but the policy is a program that
knows only the address of a policy's port and its token (decision 0061). It
depends on `greenhouse_protocol` and the standard library alone: it reads its
context, what the run's sensors delivered and what became of its actions,
and gives its plan's next revision as its own principal, never as the
operator. The port's server plays the run on the wall clock, so the policy
waits for the run's clock to reach each decision.

Run on its own, this file does what a benchmark's runner does: it starts the
port's server for the climate box's run, gives one policy a token, starts
itself as that policy in a process of its own, and stops the server. Given
`--url` and a token in `GREENHOUSE_POLICY_TOKEN`, it is only the policy.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Final

from greenhouse_protocol.actions import ActionKind, SetLevel
from greenhouse_protocol.authorisation import AuthorisationConfig, AuthorisationGroup, Grant
from greenhouse_protocol.budget import InformationBudget
from greenhouse_protocol.context import CapabilityContext, SourceKind
from greenhouse_protocol.contracts.consumer import (
    EventBatch,
    ForecastBatch,
    ObservationBatch,
    OutcomeBatch,
)
from greenhouse_protocol.contracts.gateway import Receipt
from greenhouse_protocol.contracts.policy import (
    CancelPlan,
    Decision,
    Delivery,
    Keep,
    PolicyIdentity,
    PolicyPort,
    Revise,
)
from greenhouse_protocol.contracts.policy_client import HttpPolicyPort
from greenhouse_protocol.enums import ObservationType
from greenhouse_protocol.plan import Asap, Plan, PlannedAction, Principal, PrincipalKind

SCENARIO: Final = "climate_box"
POLICY: Final = Principal(kind=PrincipalKind.POLICY, id="naive_heating")
# The policy may set levels and do nothing else.
AUTHORISATION: Final = AuthorisationConfig(
    version=1,
    groups=(
        AuthorisationGroup(
            group_id="policies",
            principals=frozenset({POLICY}),
            grants=(Grant(kinds=frozenset({ActionKind.SET_LEVEL})),),
        ),
    ),
)
HEATS: Final = "heats"
ON_BELOW_C: Final = 15.0
OFF_ABOVE_C: Final = 17.0
# A decision every five minutes of the run's clock.
STEP_S: Final = 300.0
# The plan the policy gives revisions of.
PLAN_ID: Final = "policy"
# How long the policy waits between looks at the run's clock, in seconds.
POLL_S: Final = 0.01
# The environment variable that holds the policy's token.
TOKEN_VARIABLE: Final = "GREENHOUSE_POLICY_TOKEN"
# What the demonstration run gives a simulated day, in seconds, and how long
# of the run's clock it steers.
DEMONSTRATION_SECONDS_PER_DAY: Final = 10.0
DEMONSTRATION_HOURS: Final = 2.0
# How long the demonstration waits for its server to say where it is.
SERVER_WAIT_S: Final = 120.0


def format_time(time_s: float) -> str:
    """A moment of the run as hours and minutes into it."""
    minutes = round(time_s / 60)
    return f"{minutes // 60}:{minutes % 60:02}"


def decide(reads_c: float | None, heating: bool) -> bool:
    """Whether the heater is to run from now: on while the air reads cold,
    off once it reads warm, as it was between the two or with no reading."""
    if reads_c is None:
        return heating
    if reads_c < ON_BELOW_C:
        return True
    if reads_c > OFF_ABOVE_C:
        return False
    return heating


class NaiveHeating:
    """The rule as a policy: its heater and its sensor from its context, and
    a revision of its plan each time its mind changes. It is the policy of
    example 03, so that the runner steps it in the process as well."""

    identity: Final = PolicyIdentity(name="naive_heating", version="1")
    decide_every_s: Final = STEP_S

    def start(self, context: CapabilityContext, budget: InformationBudget) -> None:
        self._principal = context.principal
        self._heater = next(d.device_id for d in context.devices if HEATS in d.does)
        self._sensor = next(
            source.source_id
            for source in context.sources
            if source.kind == SourceKind.SENSOR
            and source.quantities[0].observation_type == ObservationType.AIR_TEMPERATURE_C
        )
        self._heating = False
        self._changes = 0
        self._first: datetime | None = None

    def decide(self, at: datetime, delivered: Delivery) -> Decision:
        self._first = self._first or at
        readings = [o.value for o in delivered.observations if o.sensor_id == self._sensor]
        reads_c = readings[-1] if readings else None
        wanted = decide(reads_c, self._heating)
        reads = "   -   " if reads_c is None else f"{reads_c:4.1f} °C"
        ended = ", ".join(f"{o.ref} {o.status}" for o in delivered.outcomes) or "-"
        print(
            f"{format_time((at - self._first).total_seconds())}  {self._sensor} reads {reads}, "
            f"heater {'on ' if wanted else 'off'}; outcomes: {ended}",
            flush=True,
        )
        if wanted == self._heating:
            return Keep()
        self._heating = wanted
        self._changes += 1
        return Revise(
            actions=(
                PlannedAction(
                    action_id=f"{self._heater}_{self._changes}",
                    action=SetLevel(device_id=self._heater, level=1.0 if wanted else 0.0),
                    timing=Asap(),
                    proposed_by=self._principal,
                ),
            )
        )

    def stop(self) -> None:
        self._heating = False


class Steering:
    """The policy's plan, as it gives it: named, its revisions counted on
    from the one in force. A revision refused because the one in force is as
    new or newer is given once more after reading that one."""

    def __init__(self, port: PolicyPort, plan_id: str) -> None:
        self._port = port
        self.plan_id = plan_id
        self.revision = 0
        self.last: Plan | None = None

    def revise(self, actions: tuple[PlannedAction, ...]) -> Receipt:
        receipt = self._give(actions)
        if not receipt.accepted and self.catch_up():
            receipt = self._give(actions)
        return receipt

    def cancel(self) -> Receipt | None:
        if self.revision == 0:
            return None
        self.catch_up()
        return self._port.cancel_plan(
            self.plan_id, revision=self.revision, epoch=self._port.run().epoch
        )

    def give_again(self) -> Receipt:
        """The last revision given, once more: refused as stale."""
        if self.last is None:
            raise ValueError("no revision has been given")
        return self._port.submit(self.last)

    def catch_up(self) -> bool:
        """Counts on from the revision in force, if it is newer than the one
        given; whether it was."""
        in_force = self._port.plan(self.plan_id)
        if in_force is None or in_force.plan.revision <= self.revision:
            return False
        self.revision = in_force.plan.revision
        return True

    def _give(self, actions: tuple[PlannedAction, ...]) -> Receipt:
        run = self._port.run()
        plan = Plan(
            plan_id=self.plan_id,
            run_id=run.run_id,
            epoch=run.epoch,
            revision=self.revision + 1,
            actions=actions,
        )
        receipt = self._port.submit(plan)
        if receipt.accepted:
            self.revision += 1
            self.last = plan
        return receipt


class Reader:
    """A port's logs, read on from where the last decision left them."""

    def __init__(self, port: PolicyPort) -> None:
        self._port = port
        self._after = {"observations": 0, "events": 0, "outcomes": 0, "forecasts": 0}
        self.outcomes: list[Any] = []

    def since_last(self) -> Delivery:
        observed = self._drain("observations", self._port.observations)
        happened = self._drain("events", self._port.events)
        ended = self._drain("outcomes", self._port.outcomes)
        issued = self._drain("forecasts", self._port.forecasts)
        new = tuple(o for batch in ended for o in batch.outcomes)
        self.outcomes += new
        return Delivery(
            observations=tuple(o for batch in observed for o in batch.observations),
            events=tuple(e for batch in happened for e in batch.events),
            outcomes=new,
            forecasts=tuple(f for batch in issued for f in batch.forecasts),
        )

    def _drain[BatchT: (ObservationBatch, EventBatch, OutcomeBatch, ForecastBatch)](
        self, log: str, read: Callable[[int], BatchT]
    ) -> list[BatchT]:
        batches = [read(self._after[log])]
        while batches[-1].has_more:
            batches.append(read(batches[-1].next))
        self._after[log] = batches[-1].next
        return batches


def act(steering: Steering, decision: Decision) -> Receipt | None:
    match decision:
        case Keep():
            return None
        case Revise(actions=actions):
            return steering.revise(actions)
        case CancelPlan():
            return steering.cancel()


def steer(
    port: PolicyPort, policy: NaiveHeating, *, hours: float, repeat_first_revision: bool = False
) -> dict[str, Any]:
    """Steers the run for `hours` of its clock, deciding every
    `policy.decide_every_s` of it, and says what it gave and what came of it.
    With `repeat_first_revision`, the first revision given is given once
    more, which the port refuses as stale; the policy then reads its plan in
    force and goes on from it."""
    started = time.monotonic()
    first = port.run()
    start = first.started_at
    end = start + timedelta(hours=hours)
    policy.start(port.context(), port.budget())
    steering, read = Steering(port, PLAN_ID), Reader(port)
    decisions: list[dict[str, Any]] = []
    repeated: dict[str, Any] | None = None
    next_at = start
    try:
        while (now := port.run().clock.simulated_now) < end:
            if now < next_at:
                time.sleep(POLL_S)
                continue
            decision = policy.decide(now, read.since_last())
            receipt = act(steering, decision)
            decisions.append(
                {
                    "at_s": (now - start).total_seconds(),
                    "decision": decision.kind,
                    "receipt": None if receipt is None else receipt.model_dump(mode="json"),
                }
            )
            if repeat_first_revision and repeated is None and receipt and receipt.accepted:
                again = steering.give_again()
                caught_up = steering.catch_up()
                in_force = port.plan(PLAN_ID)
                repeated = {
                    "revision": receipt.revision,
                    "refused_again": not again.accepted,
                    "receipt": again.model_dump(mode="json"),
                    "in_force": None if in_force is None else in_force.plan.revision,
                    "newer_than_given": caught_up,
                }
            next_at = now + timedelta(seconds=policy.decide_every_s)
    finally:
        policy.stop()
    read.since_last()
    run = port.run()
    return {
        "policy": policy.identity.model_dump(),
        "run_id": run.run_id,
        "epoch": run.epoch,
        "started_at": start.isoformat(),
        "wall_s": round(time.monotonic() - started, 2),
        "decisions": decisions,
        "repeated": repeated,
        "outcomes": [o.model_dump(mode="json") for o in read.outcomes],
    }


def host() -> int:
    """Starts the port's server for the climate box's run, makes the policy a
    token, runs this file as the policy, and stops the server."""
    with tempfile.TemporaryDirectory() as folder:
        files = Path(folder)
        made = subprocess.run(
            [
                sys.executable,
                "-m",
                "greenhouse_sim.api.policy_server",
                *("--new-credential", f"{POLICY.kind}:{POLICY.id}"),
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
        token = made[0].split(": ", 1)[1]
        credential = json.loads(made[1].split(": ", 1)[1])
        (files / "credentials.json").write_text(
            json.dumps({"version": 1, "credentials": [credential]})
        )
        (files / "authorisation.json").write_text(AUTHORISATION.model_dump_json())
        log = (files / "server.log").open("w")
        server = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "greenhouse_sim.api.policy_server",
                *("--scenario", SCENARIO, "--port", "0"),
                *("--credentials", str(files / "credentials.json")),
                *("--authorisation", str(files / "authorisation.json")),
                *("--seconds-per-day", str(DEMONSTRATION_SECONDS_PER_DAY)),
            ],
            stdout=subprocess.PIPE,
            stderr=log,
            text=True,
            # Its epochs are kept here, not in the user's state folder.
            env=os.environ | {"XDG_STATE_HOME": str(files / "state")},
        )
        try:
            assert server.stdout is not None
            said = server.stdout.readline()
            found = re.search(r"at (http://\S+?)/policy/v1", said)
            if found is None:
                print(f"the port's server did not start: {said!r}", file=sys.stderr)
                return 1
            print(said.strip(), flush=True)
            return subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    *("--url", found.group(1)),
                    *("--hours", str(DEMONSTRATION_HOURS)),
                ],
                env=os.environ | {TOKEN_VARIABLE: token},
                check=False,
            ).returncode
        finally:
            server.terminate()
            server.wait(timeout=SERVER_WAIT_S)
            log.close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="A policy in a process of its own.")
    parser.add_argument("--url", help="the port's server, such as http://127.0.0.1:8770")
    parser.add_argument("--hours", type=float, default=DEMONSTRATION_HOURS)
    parser.add_argument("--record", type=Path, help="write what the policy gave and saw here")
    parser.add_argument(
        "--repeat-first-revision",
        action="store_true",
        help="give the first revision once more, to show that the port refuses it as stale",
    )
    args = parser.parse_args(argv)
    if args.url is None:
        return host()
    token = os.environ.get(TOKEN_VARIABLE)
    if not token:
        parser.error(f"the policy's token is in the environment variable {TOKEN_VARIABLE}")
    record = steer(
        HttpPolicyPort(args.url, token),
        NaiveHeating(),
        hours=args.hours,
        repeat_first_revision=args.repeat_first_revision,
    )
    print(
        f"{len(record['decisions'])} decisions, "
        f"{sum(1 for d in record['decisions'] if d['receipt'])} revisions given, "
        f"{len(record['outcomes'])} outcomes, in {record['wall_s']} s"
    )
    if args.record is not None:
        args.record.write_text(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
