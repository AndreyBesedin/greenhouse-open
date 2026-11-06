"""A kind of equipment the simulator was not written with, in a module of its
own, as another package would hold it (P14.5, decisions 0054 and 0055): a
radiant panel, which heats.

Its tests register it while each runs (`test_registered_equipment`). Run as a
program, the module registers it and serves the simulator's API, taking what
`python -m greenhouse_sim.api` takes: a simulator that places, runs and draws
it, for the browser test of P14.7's QA scenario
(`greenhouse_sim/web/e2e/models-qa.spec.ts`), whose viewer is built without
it. The simulator's workers are processes of their own, which do not
register it, so a run of it is the API's own: a worker refuses its scenario,
naming the kind."""

from typing import Literal

from pydantic import PositiveFloat

from greenhouse_sim.world.capabilities import Capability, Heats
from greenhouse_sim.world.equipment import Unit


class RadiantPanel(Unit):
    """A radiant panel standing on the floor: its power, all of it heating
    the air around its body."""

    kind: Literal["radiant_panel"] = "radiant_panel"
    power_w: PositiveFloat

    def rated(self) -> dict[str, float]:
        return {"power_w": self.power_w}

    def capabilities(self) -> tuple[Capability, ...]:
        return (Heats(power_w=self.power_w),)


if __name__ == "__main__":
    from greenhouse_sim.api.server import main
    from greenhouse_sim.world.equipment import register_equipment

    register_equipment(RadiantPanel)
    raise SystemExit(main())
