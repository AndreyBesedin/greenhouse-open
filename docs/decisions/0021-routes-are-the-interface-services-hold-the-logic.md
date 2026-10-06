# 0021: Routes are the interface; services hold the logic

**Status:** Accepted
**Date:** 2026-10-06

## Context

The local API (decision 0009) began as a few routes over the simulator. By
the end of P02 its routes held simulator logic: they loaded layout files,
rebuilt a greenhouse from a request's dimensions and openings, decided which
dimensions and openings exist, named a scenario's plants, started the engine,
and dispatched live-run commands. Each new endpoint added more, and the
logic could only be tested through HTTP-shaped requests. The projects ahead
(airflow, actuators, sensors) will add endpoints, and other interfaces, such
as a command line or another protocol, may need the same operations.

## Decision

- Every API in the repository, whatever its transport, is only an interface
  to services. A route checks that the caller may make the request, reads
  the request into the typed form its service takes, calls the service, and
  answers with the result or turns the service's error into a status.
- Services (a package's `services` subpackage) hold the logic and the case
  handling. They take typed requests, return typed results, and raise typed
  errors (`ServiceError`: `NotFound`, `InvalidRequest`, and new kinds as
  clients need different answers). They never import the API or a transport,
  and never choose a status.
- Reading a request's format belongs to the route; whether what it names
  exists, or may be done, belongs to the service. Domain rules stay in the
  domain's models.
- Each API maps service errors to statuses in one table. An unexpected
  failure is answered with the transport's internal error and logged.
- The local API has no callers to tell apart: it answers only on this
  machine. Its routes check no rights until it does; the check then comes
  first in the route, and there is no placeholder for it before.
- `scripts/check_api_layers.py` enforces the imports, as a pre-commit hook
  and a CI test, for every package: an `api` package reaches the rest of its
  package only through its `services`, and services import neither the API
  nor a transport.

## Consequences

- Services are tested directly, case by case, without HTTP; the API's tests
  shrink to reading requests and mapping answers.
- Another interface reuses the services as they are.
- A request passes through one more layer, and a new endpoint means a
  service function as well as a route.
- The check catches a route that imports domain code, not one that grows
  logic over the services' own types. Review keeps the rest.
