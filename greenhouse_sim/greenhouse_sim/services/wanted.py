"""Whether a request's work is still wanted (`greenhouse_sim.core.wanted`), as
the API, which reaches the simulator through its services, says so."""

from greenhouse_sim.core.wanted import NoLongerWanted, wanted_while

__all__ = ["NoLongerWanted", "wanted_while"]
