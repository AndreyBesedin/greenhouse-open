# 0036: The API shows people the truth; a policy reads observations only

**Status:** Accepted
**Date:** 2026-10-16

## Context

Decision 0009 says the local API "serves no ground truth", and the API's
own docstring says it never does. Since P06 it does, on purpose
([repository audit](../audits/2026-10-13-repository-audit.md), `AUDIT.26`):

- `/api/scenarios/{id}/climate/truth` answers with what each point sensor
  truly sampled, before its noise, bias, drift, latency and dropouts, so
  that the viewer's QA mode can set it beside what the sensor reported.
- The viewer draws the simulated world itself: the house's air and its
  fields, the crop, and, in the developer panel (`/climate/state`), what
  each process of the run holds.

The boundary that holds, and that matters, is another one: truth never
travels inside an observation, and a policy reads observations only
(`examples/03_close_the_loop.py`). The test behind 0009's sentence checks
only that `greenhouse_sim.ground_truth` is read by the evaluation alone
(`tests/test_dependencies.py`); the sensors' truth does not pass through
that module. The API binds to the loopback interface (0009), and no policy
reads it.

Putting the truth route behind a server flag (`--qa`), off by default, was
weighed and left for later: nothing that could cheat reads the API, and a
flag could not hide the fields and the scene, which are the simulated world
too.

## Decision

- **The API is a local tool for people.** It shows the simulated world as
  it is, and what the sensors report about it.
- **The sensors' truth leaves the API by one route,**
  `/api/scenarios/{id}/climate/truth`, for QA mode, and the viewer asks for
  it only in QA mode.
- **No observation carries truth.** A canonical observation, the
  observation log and everything a policy reads carry only what a sensor
  reports, and a policy reads nothing else. `greenhouse_sim.ground_truth`
  stays the evaluation's alone.
- A change to what serves truth is held for review: the risk gate holds
  `api/routes.py`, `services/sensors.py`, `sensors/air.py` and
  `evaluation/sensor_truth.py` (`scripts/check_pr_risk.py`).
- This replaces decision 0009's "serves no ground truth". The rest of 0009
  stands.

## Consequences

- The API's docstring says what it serves, truth included.
- QA mode, the developer panel and the golden views keep working as they
  are; nothing in the code changes.
- Worth revisiting the day a policy or an agent reads the HTTP API: the
  truth route then goes behind a server flag or a port of its own, so that
  a policy's client cannot reach it.
