"""The policy's port's server, `python -m greenhouse_sim.api.policy_server`,
whole, but for the scenarios its simulator knows: run as a program with the
same arguments, it serves the climate box cut to a short run (`short_runs`).
A process that tests the boundary between a policy and a run then takes seconds
for what the air's grid would take minutes over."""

import sys
from typing import Final
from unittest.mock import patch

from greenhouse_protocol.authorisation import AuthorisationConfig
from short_runs import cut, simulator_of

from greenhouse_sim.api import policy_server
from greenhouse_sim.scenarios.config import ScenarioConfig
from greenhouse_sim.services.simulator import Simulator

SCENARIO: Final = "climate_box"
CUT: Final[ScenarioConfig] = cut(SCENARIO)


def _simulator(authorisation: AuthorisationConfig) -> Simulator:
    return simulator_of(CUT, authorisation=authorisation)


if __name__ == "__main__":
    with patch.object(policy_server, "Simulator", _simulator):
        raise SystemExit(policy_server.main(sys.argv[1:]))
