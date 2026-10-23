"""The scenarios, and what each is before its run: its manifest, its scene,
its layout, its weather and its CFD geometry.

    GET /api/scenarios                    the registered scenarios, with the
                                          names of their layouts
    GET /api/scenarios/{id}/manifest      what a scenario's run is made from,
                                          for QA: its manifest's format and
                                          version, its seed, its days and its
                                          models; &weather= as for its climate
    GET /api/scenarios/{id}/scene         a scenario's scene before its first day;
                                          ?layout=propagation shows another of its
                                          layouts, ?envelope=length:12,spans:3
                                          changes its greenhouse's dimensions,
                                          and ?open=roof_vent_1:0.5,door_1:1 how
                                          far its doors and vents stand open, and
                                          ?set=fan:1,heater:0.5 how hard its
                                          equipment runs
    GET /api/scenarios/{id}/weather       its site, and the weather outside it &t=600
                                          seconds into a run, with the wind in
                                          the world's axes; &weather=cold_spring_day
                                          under a preset, as for its climate
    GET /api/scenarios/{id}/weather/day   its weather every ten minutes through
                                          its run's first day, or the day of
                                          &t=600
    GET /api/scenarios/{id}/cfd/geometry  the boundaries of a scenario's air as
                                          a CFD solver is given them, snapped
                                          to its mesh; changed as for its scene
    GET /api/scenarios/{id}/layout        a scenario's layout, as its file holds
                                          it; ?layout=propagation another of them
"""

from greenhouse_sim.api.responses import Response
from greenhouse_sim.api.routes.shared import Query, answer, last, pairs, seconds
from greenhouse_sim.services import cfd, scenarios, weather
from greenhouse_sim.services.simulator import Simulator


def get(simulator: Simulator, segments: list[str], query: Query) -> Response | None:
    match segments:
        case ["api", "scenarios"]:
            return answer(lambda: scenarios.scenario_summaries(simulator.catalogue))
        case ["api", "scenarios", scenario_id, "manifest"]:
            return answer(
                lambda: scenarios.run_manifest(
                    simulator.catalogue, scenario_id, last(query, "weather")
                )
            )
        case ["api", "scenarios", scenario_id, "scene"]:
            return answer(
                lambda: scenarios.initial_scene(
                    simulator.catalogue, scenario_id, scene_changes(query)
                )
            )
        case ["api", "scenarios", scenario_id, "weather"]:
            return answer(
                lambda: weather.at_a_moment(
                    simulator.catalogue, scenario_id, seconds(query), last(query, "weather")
                )
            )
        case ["api", "scenarios", scenario_id, "weather", "day"]:
            return answer(
                lambda: weather.through_the_day(
                    simulator.catalogue, scenario_id, last(query, "weather"), seconds(query)
                )
            )
        case ["api", "scenarios", scenario_id, "cfd", "geometry"]:
            return answer(
                lambda: cfd.geometry(simulator.catalogue, scenario_id, scene_changes(query))
            )
        case ["api", "scenarios", scenario_id, "layout"]:
            name = last(query, "layout")
            if name is None:
                return answer(lambda: scenarios.layout(simulator.catalogue, scenario_id))
            return answer(lambda: scenarios.layout(simulator.catalogue, scenario_id, name))
        case _:
            return None


def scene_changes(query: Query) -> scenarios.SceneChanges:
    """The changes a scene request asks for, as its query writes them."""
    changes: dict[str, object] = {
        "envelope": pairs(query.get("envelope", []), "envelope"),
        "openings": pairs(query.get("open", []), "open"),
        "levels": pairs(query.get("set", []), "set"),
    }
    name = last(query, "layout")
    if name is not None:
        changes["layout"] = name
    return scenarios.SceneChanges.model_validate(changes)
