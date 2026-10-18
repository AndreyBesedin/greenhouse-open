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
- `/api/scenarios/{id}/climate/observations?clean=1` answers with the
  observation log as clean sensors would have made it: its values are
  that truth, for the same QA mode.
- The viewer draws the simulated world itself: the house's air and its
  fields, the crop, and, in the developer panel (`/climate/state`), what
  each process of the run holds.

The boundary that holds, and that matters, is another one: truth never
travels inside an observation a policy reads, and a policy reads
observations only (`examples/03_close_the_loop.py`). The test behind
0009's sentence checks only that `greenhouse_sim.ground_truth` is read by
the evaluation alone (`tests/test_dependencies.py`); the sensors' truth
does not pass through that module. The API binds to the loopback
interface (0009), and no policy reads it.

Putting the truth routes behind a server flag (`--qa`), off by default,
was weighed and left for later: nothing that could cheat reads the API, and
a flag could not hide the fields and the scene, which are the simulated
world too.

## Decision

- **The API is a local tool for people.** It shows the simulated world as
  it is, and what the sensors report about it.
- **The sensors' truth leaves the API for QA mode only,** by two routes:
  `/api/scenarios/{id}/climate/truth`, and the clean observation log
  (`/climate/observations?clean=1`). The viewer asks for either only in QA
  mode.
- **No observation a policy reads carries truth.** A canonical
  observation, a run's observation log as its sensors make it, and
  everything a policy reads carry only what a sensor reports, and a policy
  reads nothing else. The clean log is QA mode's alone.
  `greenhouse_sim.ground_truth` stays the evaluation's alone.
- A change to what serves truth is held for review: the risk gate holds
  `api/routes.py`, `services/sensors.py`, `sensors/air.py` and
  `evaluation/sensor_truth.py` (`scripts/check_pr_risk.py`).
- This replaces decision 0009's "serves no ground truth". The rest of 0009
  stands.

## Consequences

- The API's docstring says what it serves, truth included.
- QA mode, the developer panel and the golden views keep working as they
  are; nothing in the code changes.
- Worth revisiting the day a policy or an agent reads the HTTP API. It
  then gets an interface of its own that serves observations and takes
  controls, and nothing else, so that a policy's client reaches none of
  the simulated world: not the truth route or the clean log, and not the
  fields, the crop or the run's state either. A flag on the truth routes
  alone would leave those.
