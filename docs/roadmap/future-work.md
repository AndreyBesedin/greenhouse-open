# Future work

Plans recorded on the [roadmap](README.md) that have no project of their own yet, or
have only part of one. Each keeps the date it was recorded, and what it says is as
of that date unless it names a later one. The order of what comes next is in the
[roadmap](README.md#order-of-work) and the
[research priorities](research-validation-priorities.md).

## Camera imperfections

Recorded 2026-10-08, with the headless renderer
for datasets, after P09 unless a policy needs them sooner. P06's cameras
take every frame on time, and draw perfect images. Planned then:

- frames that come late, or not at all, seeded as point sensors' readings
  are, using the protocol's `CameraFrame.delivered_at`;
- images as cameras make them: exposure, noise, motion blur and lens
  distortion, with the distortion in the camera's intrinsics.

## Climate setpoints

Recorded 2026-10-20, after P10. A target, set by a person, for the air's temperature and
humidity, which runs the house's equipment as a climate computer would.
[P11](archive/p11-climate-setpoints.md), closed on 2026-11-06, made every loop (heating,
venting, circulation, dehumidifying) the house's, decided at its edge (decision 0058), and
the heating targets a run's input. Left, from P11, each designed in its document:

- **P11.3's rest:** the venting and humidity targets as a run's input, with their units,
  ranges and dead band checked both ways, in P13's `set_target` union; and the equipment
  route naming the loop that runs each device, its state and its target.
- **P11.4, the viewer:** the Targets panel for venting and humidity (it has the heating
  targets), the loop's name in the Equipment panel, and the loops' switches in the
  timeline's air lane.
- **P11.5, the reference greenhouse by its targets:** its daily vent and fan commands give
  way to venting and humidity targets, so its run, replay, reference views and screenshots
  are written again, announced to consumers first. P13's daily commands of the reference
  run become a standing plan then.
- **P11.6, its QA scenario,** as P11's document has it, with the March and June
  measurements of its acceptance.
- **A test of two loops on one device:** a venting stage above the humidity crack, one
  loop clearing and the other's request left standing. The code does it; no test holds it.

## Crop work within the day

Recorded 2026-10-22, after [P13](archive/p13-actions.md). Automation plans and stacks
crop work through the day: a harvest at 10:00 and another at 15:00, each changing the
crop when it is done. [P16](archive/p16-crop-at-its-models-step.md) (decision 0064) did
the run's half: a crop steps at its model's step, a day or a whole divisor of one, and
its crop work is carried out at that step's boundaries. The organ crop steps a day at a
time, so its crop work is still carried out at a day's start only (decision 0046). Left:

- the organ crop stepping within a day, its organs growing between two actions, so that
  one action's effect is there for the next: a plant's contract stepping within its
  day, which decision 0024's day sets, and so a decision of its own;
- then [P16.4](archive/p16-crop-at-its-models-step.md#steps), deferred until a model
  takes crop work within its day: the plan's check and the gateway's answers by that
  model's step; the action format, which already takes any instant, unchanged.

## Actions and plans, after P13

Recorded 2026-11-06, as [P13](archive/p13-actions.md) was done. What its steps and its
final QA left open:

- **A server's crew** ([P13.6](archive/p13-actions.md#settled-in-p136)): the server takes
  no crew of its own, so its runs have none; and a hand the crop refuses an action
  for is not handed back to the actions assigned after it, which keep their instants.
- **A JSON plan in a run's request** ([P13.7](archive/p13-actions.md#settled-in-p137)): a
  plan that is part of a run's identity is still given in the address's spellings.
- **The schedule's remove and repeat**, in the viewer
  ([P13.8](archive/p13-actions.md#settled-in-p138)), which edit a followed run's own and
  so make another run, go with the viewer's own play in
  [P22.3](p22-watching-and-starting-a-run.md#steps).
- **Who cancelled, in the plan lane** (the
  [final QA](archive/p13-actions.md#recorded-at-88f35bae), step 9): the lane reads
  "cancelled: cancelled", though the outcome names who cancelled it.

## CO₂ and light targets

Recorded 2026-10-20, after the climate setpoints. Each needs equipment the
simulator does not have yet:

- **CO₂:** a CO₂ doser, adding CO₂ to the air below a target while the
  vents are shut;
- **PAR** (the light in the 400 to 700 nm band plants use, in µmol/m²/s):
  grow lamps, lighting the crop below a target by day length or by the
  light the sun gives, their light reaching the crop as the sun's does
  (P08) and their heat the air. The reference greenhouse's PAR is the
  sun's alone, so it falls to 0 every night.

## Intelligence components

Recorded 2026-10-24, after the projects then in progress, P11 to P14. The components
that decide and predict from what a greenhouse observes: a climate strategy that sets
its targets, crop work planned from the crop's state, a yield forecast, the crop seen in
its cameras' images. Decision
[0061](../decisions/0061-greenhouse-decisions-are-benchmarked-through-interfaces-built-for-it.md)
gives them one foundation, control policies first, and settles where an outside one runs,
how its identity enters an experiment's, and how policies are compared;
[P15](archive/p15-policy-port.md), its stage A, built the policy's port, and the benchmark
of control policies is item 7 of the [research priorities](research-validation-priorities.md).
Left here:

- **Forecasts and perception,** on the same foundation, giving typed, timestamped
  records evaluated by measures of their own (decision 0061). P15's port serves
  forecasts from named providers, persistence the first.
- **Base components in the simulator,** behind that interface: simple,
  documented with their limits, as its base models are, so that a run, a
  policy's evaluation and the viewer work with nothing from outside. A
  harvest planner and a forecast from a crop model are the first candidates;
  a rule-based climate strategy is the research priorities' conventional baseline.
- **The most complex components from outside,** proprietary or public,
  through the same interface: the repository holds their contract and its
  conformance tests, and evaluates them against its ground truth, not the
  components themselves.

## Crop models from plant research

Recorded 2026-10-24, after P14, whose registry lets a manifest choose a crop model;
ordered by decision 0057 on 2026-10-27. The tomato's survey is
[the tomato model memo](../research/tomato-model-feasibility.md); its two models,
Reduced-State TOMGRO and Vanthoor's as Katzin simplified it (decision
[0060](../decisions/0060-two-published-tomato-models-become-crop-models-of-the-run.md)),
are reproduced, made crop models of the run and held to measured data as items 4 and 5
of the [research priorities](research-validation-priorities.md) have it, the organ and
simple models kept beside them as baselines. Left here:

- **Then cucumber, strawberry and sweet pepper,** once the tomato's
  reproductions have tested the registry's crop interface: a survey of each
  first, then each a crop model of the registry, with its parameters for
  each variety (P20), its organs drawn by the viewer, its records (fruit
  counts and mass) in the protocol's terms, and a conformance test with
  the crop part's other models.
- **Each model held to its sources:** the data it was validated against
  kept as a reference test, where its licence allows.

## Models and devices, after P14

Recorded 2026-11-06, from [P14.7's QA](archive/p14-models-by-manifest.md#recorded-at-67a8cebc),
none of them P14.7's own. Planned then:

- **A registered kind in a stored run.** A kind of equipment registered by a module the API
  imports is not known to the workers the API spawns, so a stored run of a house that has one
  fails before its first day ("no kind of equipment 'radiant_panel'"), though the viewer's
  climate runs use it. The workers register what the API does, or entry points come (decision
  0054's open question 3).
- **The builder and a kind it was not built with:** it opens no such house, since its forms are
  read from the published schema, which names the kinds the simulator was written with; the
  viewer draws, lists and runs it.
- **A checkpoint uploaded into another scenario's panel** is kept for the scenario it names,
  without a word: the panel says whose it is, or refuses one that is not its scenario's.
- **The builder's run step for an uploaded copy** offers its own start and seed (1 April, 0)
  rather than the file's (1 March, 42).

## Runs and playbacks, after P17

Recorded 2026-11-06, as [P17](archive/p17-runs-and-playbacks.md) closed (decisions 0065
and 0066). Left, from P17, each designed in its document:

- **A `present` store** (P17.6, its QA's step 6): an epoch that keeps only a window `W`
  behind its frontier, the newest checkpoint at or before `F - W` and what follows it,
  so that a batch of runs for training keeps about 0.2 to 0.4 MB at day 120 in place of
  11 to 24 MB. Its invariant and its measurements are in P17's design and its P17.1
  record. Every epoch is kept whole today, and the viewer's header says so.
- **The consumer interface and the policy port reading a stored epoch** (P17.4, P17.7):
  they read the live playbacks, so a consumer follows a run its server plays, not an
  epoch a worker computes or one kept from before a restart. Whether the playbacks stay
  for them is [P22.3](p22-watching-and-starting-a-run.md#steps)'s decision.
- **A crop action still under way at a kept state** (P17.8, P17.9): a fork or a resume
  from a state kept while a crew was still at an action is refused, since nothing kept
  says what the action did. A crew's work in progress kept with the checkpoint would let
  both go on.
- **An epoch stepped by a caller** (P17.9) is carried on only by that caller, as an
  experiment steps it; a worker does not take it up.

## Resources and limits, after P18

Recorded 2026-11-08, as [P18](archive/p18-resources-and-deployment.md) closed (decision
0067). Left, from P18, each in its step's row or its final QA:

- **A playback in the API's process has no limits** (P18.3): it opens an epoch with no
  budget, and `--play` is not refused. Whether such playbacks stay at all is
  [P22.3](p22-watching-and-starting-a-run.md#steps)'s decision.
- **One store, several servers** (P18.4): each server keeps its own limit on workers and
  its own count of what waits, so that two on one folder can pass the limit between them.
  A worker that a killed server started is not counted until it claims its epoch.
- **A holder stalled past its claim** (P18.4): one stopped for over 30 s, as on a machine
  asleep, whose epoch is taken over, is not stopped, and its writes still reach the store.
- **A worker's look at its memory is a thread** (P18.3), which a long call holding the
  interpreter delays, and the leases' thread with it.
- **The room leaves out the store's bytes** against their limit (P18.5); only the refusal
  names them.
- **What is kept after a run goes** (P18.1, P18.4): a scenario's file stays when the last
  epoch naming it is deleted, and an epoch keeps the two small objects of each working
  until it is deleted.
- **The defaults,** from P18's open questions: 200 runs waiting and a 2 GB floor are
  judgements, not measurements. A training batch would raise the first, and a small disk
  the second.
- **A budget in days or in time,** also an open question there: P18 limits an epoch by
  wall time, which ties its end to the machine; a limit in days is smaller and
  reproducible.
- **Not measured** (P18.6): a disk filled for real, and one that fills while a worker
  writes; memory past a limit on macOS; the viewer drawing in software beside the
  workers, on a machine without a graphics card; the list of 1,000 runs on the M2 again.

## Greenhouse R&D workflows and Modelica comparison

Recorded 2026-10-24, exploratory work after P14, alongside the crop-model
research above; its first comparison is item 6 of the research priorities.
Modelica and its tools, including OpenModelica and Dymola, already support
substantial greenhouse climate, energy and crop models. The question is not whether the simulator can replace
their equation-based modelling. It is whether it adds a useful *experimental
workflow* for academic and applied R&D teams, alongside existing models:
setting up a greenhouse, choosing fidelity, replaying a season, connecting
sensors and policies, and comparing decisions reproducibly.

- **Establish actual research workflows first.** Describe two or three
  representative tasks performed by academic or industrial greenhouse R&D
  teams, using existing tools as a baseline. Ask practitioners which work is
  straightforward in Modelica, which work requires custom scripts or other
  platforms, and where switching tools would cost more than it saves. Include
  unsuccessful or negative evidence, not only prospective use cases.
- **Reproduce one published scientific baseline.** A candidate is
  [TiGwerLib v0.7.0](https://zenodo.org/records/15590404), associated with
  [Sourisseau et al. (2026)](https://doi.org/10.1371/journal.pone.0340619)
  and its [published greenhouse dataset](https://zenodo.org/records/17554203).
  First attempt its documented configuration in OpenModelica, without
  requiring a proprietary license. Record exact versions of the model,
  libraries, solver, weather, measured inputs and equipment schedules, and
  report any reproduction or compatibility blockers rather than concealing
  them. Check the artefacts' licences before redistributing anything.
- **Reproduce a bounded paper result before the whole model.** For the
  [2026 global-model paper](https://doi.org/10.1371/journal.pone.0340619),
  first inventory TiGwerLib's data, executable model and published figures;
  then replicate a short measured period of indoor temperature and relative
  humidity, with explicit equipment status and weather inputs. Extend to CO₂,
  utilities or crop yield only when the corresponding inputs and processes
  can be aligned. The second candidate is the team's
  [2025 radiation view-factor paper](https://doi.org/10.17660/ActaHortic.2025.1426.1):
  reproduce one documented geometry/view-factor case where methods and data
  are accessible, separately from the global climate run. Its full text and
  reproduction assets must be checked first; an unavailable method is a
  recorded blocker, not a licence to invent missing values.
- **Compare on matched inputs, not visual similarity.** Run a comparable
  greenhouse in this simulator with the same period, weather forcing,
  geometry and equipment/control assumptions where possible. Compare indoor
  temperature, humidity, CO₂, energy and crop outputs only when definitions
  and available measurements support a meaningful comparison. Publish units,
  sampling intervals, error metrics, run times and missing physics. Different
  model fidelities are expected; disagreement is evidence about assumptions,
  not automatically a defect in either tool.
- **Test the end-to-end experiment, not just the solver.** Measure the work
  needed to configure a setup, exchange models, change sensors or actions,
  rerun counterfactual scenarios, connect a policy, evaluate it against
  hidden ground truth and reproduce its results. Distinguish capabilities
  Modelica tools already provide from those that need custom integration, and
  record where this simulator is worse or incomplete. A small, repeatable
  research task is more useful than a broad feature checklist.
- **Get feedback in two stages and decide based on evidence.** Discuss
  Modelica R&D workflows with a Greenhouses Library maintainer early, before
  presuming the current simulator offers unique value. After the first
  reproducible comparison, share its methods, findings and limitations with
  the Nantes/Angers paper authors and invite corrections or a technical
  discussion; also seek an applied/industrial R&D perspective where
  available.
  Publish a concise comparison with a reproducible reference case,
  performance/fidelity findings, workflow friction, limitations and a clear
  conclusion: complementary research workflow, a justified external-model
  adapter, or no demonstrated additional value yet. Consider FMI/FMU support
  only if a concrete workflow requires it; an integration decision then gets
  its own decision record and implementation project.

The outcome is a research comparison and a direction, **not** a replacement
of the Python simulator, a mandatory Modelica dependency, or a commitment
to buy Dymola.

## Test suite and CI time

Recorded 2026-10-08, after P09, with passes on 2026-10-24 and 2026-11-03. Done since: the
simulator's tests in a process per core (pytest-xdist, #185); the browser tests in lanes
(decision 0032), cut again by their measured times (decision 0071, #618); a pull request
leaving out the tests marked `slow`, which main runs
([engineering](../engineering.md#local-checks), #512), and the long tests of logic moved
to short runs (#514, #515). The nine successful CI runs of pull requests with 0071's lanes
that ran the long jobs, all on 2026-11-06, took 5.6 to 6.9 minutes. Left:

- **The aim:** a pull request's checks under 10 minutes, measured as successful CI runs of
  pull requests, start to finish, leaving out those under three minutes, which skip the
  long jobs; and kept there.
- **The options not taken yet:** a pull request's browser tests chosen by what its change
  can reach, or one quick check per area, with the whole suite on `main` and on a
  schedule; mypy's cache, and the browser install, kept between runs; the slowest tests
  made shorter where what they check allows.

### Documents checked against the published schemas

Recorded 2026-11-06, from [P13.1](archive/p13-actions.md#settled-in-p131). The tests hold each
of the protocol's published schemas to its record's export, but check no document
against a schema: that waits for a JSON Schema validator as a development dependency.

## A second repository audit

Recorded 2026-10-24, after the items above, the intelligence components and the
crop models from plant research included. The
[repository audit](../audits/2026-10-13-repository-audit.md) of 13 October looked at
the repository after P09. Since then the consumer's interface (P10), the climate
targets (P11), the setup builder (P12), the actions and plans (P13), the models'
registry (P14), the policy's port (P15) and the runs' store (P17) have come; by the
second audit, three more crops will have too. The second audit takes the first's
form: the commit it looked at, what it measured, findings with identifiers, and an
order of work. It asks:

- whether the first audit's findings stay closed;
- what the projects since have added that repeats, crosses a boundary, or
  is missing its tests, documents or recipes;
- whether the setup builder's and the registry's interfaces are complete
  and checked enough for the assistant below to drive them;
- the checks' time, against the aim above.

Its work plan is the maintenance done before the assistant, scheduled by
the roadmap as the first audit's was.

## An assistant in the viewer

Recorded 2026-10-24, after the
second audit's work plan. A chat that guides a person through the
simulator and helps with what it can do: setting up a new greenhouse in
the setup builder (P12), choosing the devices and sensors suited to it,
choosing a crop model from the registry (P14) or defining a new one. It
runs on a language model, called through its provider's API. It is
designed in detail when it starts, in its project document and a
decision; recorded now:

- **The user's own key:** the provider's API key, set in the user's
  `.env`, read by the simulator's server and never sent to the browser.
  Without one, the simulator and the viewer work as they do now, with no
  assistant.
- **Limits for a hosted demo:** a demo deployment that anyone can open
  runs the assistant on its own key, so its cost has a ceiling: a limit
  for each user and one for the whole deployment, enforced by the server,
  and protection from abuse, from automated or malicious traffic to
  requests that use the assistant for anything but the simulator.
- **An evaluation before it is offered:** a fixed set of requests, scored
  on what the simulator can check, such as a setup that loads, runs and is
  what was asked for; a judged score, where one is needed, labelled as
  judged, with its limits.
- **To decide with it:** the providers and models it supports; whether it
  changes a setup itself or proposes changes the person applies; what it
  is told of a scenario and a run; and how the demo tells one user from
  another.
