"""The plant lab: a row of tomato plants from the organ-level model, run
day by day, as a query asks (`lab_run`).

    GET /api/plants/scene                 the plant lab's scene: a row of tomato
                                          plants from the organ-level model;
                                          ?day=12 on another day of the lab's
                                          run, ?seed=7 drawn from another seed,
                                          ?environment=cool_dim in another of
                                          its environments, &versus=warm_bright
                                          every second plant in another, and
                                          &act=30:p01:remove_leaf:p01_n02_leaf
                                          a crop action at that day's start
                                          (repeatable), spelled as a run's
                                          &crop= is: harvest_ripe,
                                          harvest_fruit, harvest_truss,
                                          lower_stem, lower_cm or remove_leaf,
                                          and what each acts on
    GET /api/plants/structure             one of the lab's plants, organ by organ;
                                          ?plant=p07 another plant, and the rest
                                          as for its scene
    GET /api/plants/checks                what is wrong with each of the lab's
                                          plants on a run's day, by the
                                          structure's rules and since the day
                                          before; the run as for its scene
    GET /api/plants/environments          the lab's environments, by name
"""

from typing import Final

from greenhouse_sim.api.responses import Response
from greenhouse_sim.api.routes.shared import Query, answer, last, whole
from greenhouse_sim.services import plants
from greenhouse_sim.services.errors import InvalidRequest
from greenhouse_sim.services.simulator import Simulator

# A scheduled action's parts: its day, plant, kind and target.
LAB_ACTION_PARTS: Final = ("day", "plant", "action", "organ")


def get(_simulator: Simulator, segments: list[str], query: Query) -> Response | None:
    match segments:
        case ["api", "plants", "scene"]:
            return answer(lambda: plants.scene(lab_run(query)))
        case ["api", "plants", "structure"]:
            plant_id = last(query, "plant") or plants.LAB_PLANT_ID
            return answer(lambda: plants.structure(lab_run(query), plant_id))
        case ["api", "plants", "checks"]:
            return answer(lambda: plants.checks(lab_run(query)))
        case ["api", "plants", "environments"]:
            return answer(
                lambda: {
                    name: e.model_dump(mode="json") for name, e in plants.environments().items()
                }
            )
        case _:
            return None


def lab_run(query: Query) -> plants.LabRun:
    """The plant lab's run a query asks for: day 0, the lab's own seed and
    its reference environment, unless it says."""
    return plants.LabRun(
        day=whole(query, "day", 0),
        seed=whole(query, "seed", plants.LAB_SEED),
        environment=last(query, "environment") or plants.REFERENCE,
        versus=last(query, "versus"),
        actions=tuple(_lab_step(text) for text in query.get("act", [])),
    )


def _lab_step(text: str) -> plants.LabStep:
    """A crop action of the run as a query writes it: `day:plant:action:organ`,
    its action one the lab carries out (`plants.LAB_KINDS`)."""
    parts = text.split(":")
    if len(parts) != len(LAB_ACTION_PARTS) or not parts[0].isdigit():
        raise InvalidRequest(f"act wants day:plant:action:organ, not {text!r}")
    day, plant_id, kind, target = parts
    return plants.lab_step(int(day), plant_id, kind, target)
