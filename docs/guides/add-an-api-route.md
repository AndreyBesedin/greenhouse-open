# Add an API route with its service

The simulator's local API (`greenhouse_sim/greenhouse_sim/api/`) is only an
interface to its services. A route reads the request into typed values, calls
a service and answers with its result or its refusal; the service holds the
logic ([decision 0021](../decisions/0021-routes-are-the-interface-services-hold-the-logic.md),
and the APIs section of [the engineering conventions](../engineering.md#apis)).
The timeline's route is an example (commit `3f33ace`): a domain module, a
service, an arm in `respond`, and their tests.

## Steps

1. **The domain's rules** go in the module that owns them, not in the
   service: the timeline's are in `greenhouse_sim/greenhouse_sim/core/timeline.py`.
2. **The service**, in `greenhouse_sim/greenhouse_sim/services/`, a module
   of its own or the one that owns the subject:
   - a typed function that takes what the route has read (a scenario's
     identifier, a layout's name, levels, commands, moments) and returns a
     frozen pydantic model;
   - the scenario looked up with `scenario` and `changed`
     (`greenhouse_sim/greenhouse_sim/services/scenarios.py`), and moments
     checked with `checked_moment` or `checked_window`
     (`greenhouse_sim/greenhouse_sim/services/runs.py`);
   - each refusal an `InvalidRequest` or a `NotFound`
     (`greenhouse_sim/greenhouse_sim/services/errors.py`), with a message
     the client can act on. A client that needs another answer gets a new
     subclass of `ServiceError`, and a row in `_REFUSALS` in
     `greenhouse_sim/greenhouse_sim/api/routes.py`, before its base class.
3. **The route**, in `greenhouse_sim/greenhouse_sim/api/routes.py`:
   - a `case [...]` arm in `respond` for a GET, or in `_posted` for a POST,
     before `case _`. A literal segment's arm goes before an arm that
     captures any segment in the same place;
   - the query read with the helpers beside it (`_last`, `_pairs`,
     `_commands`, `_daily`, `_seconds`, `_since`), and a new syntax read by
     a new helper there, which raises `InvalidRequest`;
   - the call wrapped in `_answer`, which answers a model, a list of models
     or a dictionary, and turns a service's error into its status.
4. **The route's line in the table** at the top of
   `greenhouse_sim/greenhouse_sim/api/routes.py`: its method and path, and
   what it answers. `greenhouse_sim/tests/test_route_table.py` fails when
   the table and the routes disagree.
5. **Its tests:** the service called directly, and the route through
   `respond("GET", "/api/scenarios/climate_box/…")`, its status and body,
   refusals included, as `greenhouse_sim/tests/test_timeline.py` does.
6. **Say so:** a line in `CHANGELOG.md`'s Unreleased section if clients
   will use it, and in `greenhouse_sim/web/README.md` if the viewer does.

The API's server (`greenhouse_sim/greenhouse_sim/api/server.py`) needs no
change. The consumer interface (`greenhouse_sim/greenhouse_sim/api/consumer.py`,
decision 0040) is the protocol's, with its own rules: a route for clients
of a run goes there only by that decision.

## Tests

```bash
uv run pytest greenhouse_sim/tests/test_<subject>.py greenhouse_sim/tests/test_api.py \
  greenhouse_sim/tests/test_route_table.py
uv run pytest tests/test_api_layers.py
uv run check --fast
```

## What else to know

- **Imports:** `scripts/check_api_layers.py` (a pre-commit hook and a test)
  lets the API reach the simulator only through `greenhouse_sim.services`,
  so a type the route needs comes from a service. Services, in turn, never
  import the API or `http`, nor choose a status.
- **Unknown parameters** are ignored, and blank values dropped, as
  `parse_qs` reads them: a parameter the route does not read is not an
  error.
- **A result that becomes a contract** the viewer validates is published as
  a schema: a `*_json_schema()` beside the model, listed in
  `greenhouse_sim/tests/test_published_schemas.py`, and its types generated
  by `npm run generate` in `greenhouse_sim/web`.
- **The risk gate:** `greenhouse_sim/greenhouse_sim/api/routes.py` is a
  sensitive file, so the pull request asks for a manual review of its whole
  diff.
