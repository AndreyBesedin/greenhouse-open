"""A crop model's parameter sets (P20.4, decision 0077): listed, read,
compared, downloaded, saved and uploaded.

    GET /api/parameter-sets/{model}                    the model's sets, its
                                                       published one first
    GET /api/parameter-sets/{model}/schema             the schema of its
                                                       parameters, which a
                                                       set's form is drawn
                                                       from (P20.5)
    GET /api/parameter-sets/{model}/{name}/{version}   one, with every value
                                                       it resolves to
    GET /api/parameter-sets/{model}/{name}/{version}/compare/{name}/{version}
                                                       two, parameter by
                                                       parameter
    GET /api/parameter-sets/{model}/{name}/{version}/file
                                                       one as its file, to
                                                       download
    POST /api/parameter-sets/{model}                   a set's file, the JSON
                                                       body, without its
                                                       version: saved under
                                                       its name's next
    POST /api/parameter-sets/upload                    a set's file, the body,
                                                       kept under its own
                                                       name and version
"""

from greenhouse_sim.api.responses import Response
from greenhouse_sim.api.routes.shared import Query, answer, json_body, set_version, text_body
from greenhouse_sim.services import parameter_set_library as library
from greenhouse_sim.services.simulator import Simulator


def get(simulator: Simulator, segments: list[str], _query: Query) -> Response | None:
    match segments:
        case ["api", "parameter-sets", model]:
            return answer(lambda: library.model_sets(simulator, model))
        case ["api", "parameter-sets", model, "schema"]:
            return answer(lambda: library.parameters_schema(model))
        case ["api", "parameter-sets", model, name, version]:
            return answer(
                lambda: library.parameter_set(simulator, model, name, set_version(version))
            )
        case ["api", "parameter-sets", model, name, version, "file"]:
            return answer(lambda: library.download(simulator, model, name, set_version(version)))
        case ["api", "parameter-sets", model, name, version, "compare", other, other_version]:
            return answer(
                lambda: library.compare(
                    simulator,
                    (model, name, set_version(version)),
                    (model, other, set_version(other_version)),
                )
            )
        case _:
            return None


def post(simulator: Simulator, segments: list[str], _query: Query, body: bytes) -> Response | None:
    match segments:
        case ["api", "parameter-sets", "upload"]:
            return answer(lambda: library.upload(simulator, text_body(body)))
        case ["api", "parameter-sets", model]:
            return answer(lambda: library.save(simulator, model, json_body(body)))
        case _:
            return None
