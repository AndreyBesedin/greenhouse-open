"""A scenario's house under another crop parameter set (P20.5, decision 0077).

A scenario registered from a draft or a file runs under another of its crop
model's sets, its published one or one the simulator keeps, as a scenario of
its own: the same house, season, site, weather and seed, its crop section
naming that set, registered under an identifier made of the scenario's and
the set's (`{scenario}_{set}_v{version}`) and listed beside it. It is then
looked up, carried and told apart as every scenario whose crop names a set
is (`parameter_sets.with_parameter_set`, P20.3): its runs by the set's
digest, its manifest answer naming the set, and each epoch of it carrying
the set in its scenario's file, for its worker, a resume and a fork.

A set is its scenario's, as its crop is (decision 0075), not its run's, as
a weather is: a run under another set is a run of another scenario, not
another run of the same one. A packaged scenario runs its model's published
set alone (`parameter_sets.PACKAGED_RUNS_PUBLISHED`): its house runs under
another once the builder has made a scenario of it.
"""

import logging
from typing import TYPE_CHECKING

from greenhouse_sim.scenarios.catalogue import ScenarioRefused
from greenhouse_sim.scenarios.crop_parameters import ReducedTomgroCrop, VanthoorKatzinCrop
from greenhouse_sim.services.errors import Conflict, InvalidRequest, NotFound
from greenhouse_sim.services.parameter_sets import kept_sets, scenario_set, with_parameter_set
from greenhouse_sim.services.scenarios import ScenarioSummary, scenario_summary

if TYPE_CHECKING:
    # Typed only: the simulator imports the services that take it.
    from greenhouse_sim.services.simulator import Simulator

logger = logging.getLogger(__name__)


def under_set(
    simulator: Simulator, scenario_id: str, parameter_set: str, parameter_set_version: int
) -> ScenarioSummary:
    """The scenario of `scenario_id`'s house under the set `parameter_set`
    v`parameter_set_version` of its crop model, registered with the
    simulator and answered as the scenario list shows it: the scenario
    itself for the set it grows already, and the one registered when asked
    again. Not found for a scenario the simulator does not have; refused for
    a crop with no sets, for a packaged scenario, saying why, and for a set
    the simulator neither publishes nor keeps, by field; a conflict if the
    identifier it would take is another scenario's."""
    entry = simulator.catalogue.entry(scenario_id)
    if entry is None:
        raise NotFound(f"no scenario {scenario_id!r}")
    own = scenario_set(entry)
    section = entry.config.crop
    if own is None or not isinstance(section, ReducedTomgroCrop | VanthoorKatzinCrop):
        raise InvalidRequest(
            f"{scenario_id!r} grows the {section.kind} crop, which has no parameter sets"
        )
    if (own.name, own.version) == (parameter_set, parameter_set_version):
        return scenario_summary(simulator.catalogue, scenario_id)
    if own.fixed is not None:
        raise InvalidRequest(
            f"{scenario_id!r} runs {own.name} v{own.version}: {own.fixed}",
            [("parameter_set", own.fixed)],
        )
    named = f"{parameter_set} v{parameter_set_version}"
    asked = entry.config.model_copy(
        update={
            "greenhouse_id": f"{scenario_id}_{parameter_set}_v{parameter_set_version}",
            "name": f"{entry.config.name} under {named}",
            "crop": section.model_copy(
                update={
                    "parameter_set": parameter_set,
                    "parameter_set_version": parameter_set_version,
                    "carried": None,
                }
            ),
        }
    )
    config = with_parameter_set(asked, kept_sets(simulator.runs))
    try:
        registered = simulator.catalogue.register(config)
    except ScenarioRefused as error:
        raise Conflict(str(error)) from None
    logger.info(
        "scenario sets: %s under %s runs as %s",
        scenario_id,
        named,
        registered.scenario_id,
        extra={"event": "registered", "label": registered.scenario_id},
    )
    return scenario_summary(simulator.catalogue, registered.scenario_id)
