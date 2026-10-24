# Changelog

All three packages share a version while the protocol settles. The format
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the
project uses [semantic versioning](https://semver.org/): a change that
breaks the conformance checks is a major version.

Each version's entries are written at its release, from the descriptions of
the pull requests merged since the one before, each giving its own under
`## Changelog` (decision 0056); no pull request edits this file. The
Unreleased section holds the entries written here before that.
`uv run release changes` prints what the next release would say.

## Unreleased

- viewer: a scenario whose rows grow the simple crop draws its crop as it
  stands at the moment of its run, as it draws the organ crop, once a day
  has ended: each plant a cylinder as tall as its stem stands, in place of
  its transplants, and, selected, its numbers in the inspector (its age,
  height, trusses, fruits, ripe fruits and harvest) (P14.3).
- `greenhouse-sim`: the simple crop is a rung of the run (P14.3, decision
  0035). A scenario whose rows grow it grows it in its run, a day at a
  time, from each day's mean air temperature in its house, by its settings
  and seed: for the same temperatures, its plants are the engine's day's.
  - Its crop's scene (`GET /api/scenarios/{id}/crop`) draws its plants as
    they stand, each with its numbers; the light on its plants
    (`GET /api/scenarios/{id}/climate/plants`) is read with their crowns as
    tall as they stand that day.
  - A checkpoint keeps its plants, with the values the model keeps for
    them, and the days they lived (`models.crop.state`); a run carries on
    from it, and one whose plants could not be its run's is refused. The
    replay's probes digest its plants.
  - The crop part has a contract, `CropRung` (`biology.crop_contract`),
    which the organ crop (`core.crop.OrganRung`) and the simple crop
    (`core.simple_crop.SimpleRung`) keep, and `RunCrop` is built with one.
    The simple model's day takes the day's mean air temperature, the one
    thing it reads.
  - The simple crop's version is 2, so the run ids of the scenarios that
    grow it change, in this release; a checkpoint of one of them made
    before is refused, naming the crop.
  - A plant of the simple crop has no structure to list
    (`GET /api/scenarios/{id}/crop/{plant}` is not found for it), its root
    zone empties as the model has it, since nothing waters it in a run,
    and the crop log has no records of it.
- `greenhouse-sim`: a scenario's configuration holds its crop model's
  parameters and its crop walk's each in a section of their own (P14.3,
  decision 0054), in place of the 21 settings at its top:
  `ScenarioConfig.crop`, the parameters of the model its rows grow,
  `SimpleCrop` or `OrganCrop`, told apart by their `kind`
  (`scenarios.crop_parameters`); and `ScenarioConfig.crop_walk`, the
  walk's three measurement noises. A configuration given its crop model
  alone takes that model's parameters. `ScenarioConfig.simple_crop` gives
  the settings the engine's day grows the simple crop by: its crop's, or
  the simple crop's defaults where its rows grow the organ crop. A
  manifest's section of the organ crop takes no parameters, and a format 4
  manifest of organ rows leaves out the simple crop's settings it wrote.
  A configuration given those settings at its top, as one written before
  holds them, reads them into their sections, the simple crop's left out
  where its rows grow the organ crop. They are read from the sections:
  `config.water_capacity_ml` becomes `config.simple_crop.water_capacity_ml`,
  and `config.height_noise_cm` `config.crop_walk.height_noise_cm`. The run
  ids change with it, in this release, with P14.2's change below.
- `greenhouse-sim`: **every run id changes, once in this release** (P14.2
  and P14.3, decision 0054).
  A run's identity now covers the model each part of it runs and that
  model's version, so that a model whose numbers change makes other runs:
  the same request names another run than before, for every packaged
  scenario. A consumer that kept run ids, or records keyed by them, finds
  them under new ids. Each registered model has a version, 1 for all
  today. `GET /api/scenarios/{id}/manifest` answers each part's model and
  version, `{"model": …, "version": …}`, and QA mode shows them.
  Checkpoints are written in format 5: each part's model, its version and
  its state, the organ crop's plants and the days they lived under
  `models.crop.state`. A checkpoint made with another model or version of a
  part is refused, naming the part, a run under another weather than its
  scenario's having that weather's model. A format 5 checkpoint names
  every part's model; formats 2 to 4 are still read, as made with the
  first version of each model, a format 4 checkpoint's plants as its organ
  crop's state.

- `greenhouse-sim`: a scenario's manifest names the model each part of
  its runs runs, from a registry (P14.1, decision 0054). Manifest format 5
  adds `models`: for the weather, the air field, the crop and the crop
  walk, a model by name and its parameters, checked by that model's
  parameter model (`scenarios.registry`); a part left out runs its
  default. The weather, the airflow, the simple crop's settings and the
  walk's measurement noises are no longer written at a manifest's top, and
  format 4 manifests are migrated so. A section gives its
  parameters if its model has one with no default, as a recorded
  weather's file, and the published schema now requires them.
  `GET /api/scenarios/{id}/manifest` answers `models`, each part's model
  by part, and QA mode shows them. No run changes: every run id is the
  same. The packaged scenarios' versions change with their rewritten
  manifests, so a checkpoint of a packaged scenario downloaded before is
  refused on upload, as one of another version of its manifest is.
- viewer: the builder's inspector shows a number to twelve significant
  digits, so that a float's rounding no longer shows, as in the starting
  house's rows' origin, 2.4000000000000004. A value left as it is still
  sends nothing, and the simulator keeps it exact.
- `greenhouse-sim`: a playback's run carries out the crop actions given to
  its gateway (P13.5, decision 0046), through `Playback.submit`. A harvest,
  a lowering, a leaf removed or an inspection is carried out at the start
  of a day after its first, given by the time the clock reaches it; one
  waiting for another at that instant is done after it, that day. The gateway
  refuses the rest at once, in the run's words: watering, because its
  organ crop has no water in its root zone, and any other moment. Each
  action is done once its day is worked out, with the effect the crop gave
  it, or refused in the organ model's words. Each one done makes an event
  of its own, which names it and which its outcome names. The crop work's
  harvest events count the harvest round alone.
- `greenhouse-sim`: who may act on a simulator's runs is an authorisation
  it is given (P13.4, decision 0052): a file the server reads,
  `--authorisation <file>`, as the protocol writes the record, or else the
  local operator's, who may do every kind. The local API acts as the local
  operator; an action it may not do is refused, saying who may not do
  what. A simulator given another while its runs play has each playback
  enforce it from its clock on, recorded beside each plan
  (`Playback.plan`); an action whose rights are withdrawn before it falls
  due is refused then.
- `greenhouse-protocol`: an executor may say why it refuses
  (`contracts.execution.ExplainsRefusals.why_not`): a kind it does not
  carry out, or an instant it does not honour. The reference gateway adds
  those words to its own refusal, and `check_executor` holds them to the
  executor's kinds and the instants it honours. An execution report may
  name the event its action made in the run's records
  (`ExecutionReport.event_id`), if the action started, and the gateway's
  outcome names that event too. Both are additive (P13.5, decision 0046).
- `greenhouse-sim`: a run's plan holds crop actions (P13.5, decision 0046):
  a harvest, a lowering, a leaf removed or an inspection, at the start of a
  day after its first, on an organ crop. Any other moment is refused, in
  the run's words, and so are a plant it does not have and a lowering to a
  head room on a plant with no wire. After that day's crop work, the crop
  carries them out in the plan's order, and keeps what each did
  (`RunCrop.worked_on`). A run with crop actions has an identity of its
  own. Every other run keeps its id, replay digest and kept opening day. A
  crop takes over another's days, or a kept state's plants, only as far as
  their crop actions agree.
- `greenhouse-sim`: the organ crop carries out the protocol's crop actions
  (P13.5, decision 0046): a harvest of one fruit, one truss or every ripe
  fruit, a lowering by internodes, by centimetres or to a head room under
  the plant's wire, and a leaf removed, each as the organ model's own
  operations, with its effect: the fruits picked and their mass, how far
  the top came down, the leaf removed (`core.crop_actions`). The plant
  lab's scheduled actions and a scenario's crop work are carried out so,
  with every plant, run id and kept opening day as before. The lab refuses
  a scheduled action that names no organ. The organ model's `PlantAction`
  is renamed `PlantOperation`, and so is its definition in the plant
  schemas; its events' `action` field and kinds are unchanged.

## 0.4.0 - 2026-10-24

The setup builder (P12.0 to P12.3): a greenhouse's installation drafted
from a form or copied from a scenario, assessed as it is edited, its
equipment, sensors, doors, vents, zones and fixtures placed many at a time
and set in an inspector, kept as drafts with their revisions, exchanged
as a file, and run as a scenario of its own, in the viewer's `/builder`.
One format for acting on a greenhouse (P13.1 to P13.3, decision 0046):
the protocol's actions, plans, authorisation and outcomes, with a run's
gateway and its executors held to conformance checks; a run carries out a
plan, and a playback is its run's gateway, whose outcomes a consumer reads.
A simulator owns its scenarios, runs and playbacks (decision 0048), and
the viewer's panels fold to a stripe and sit in cards by topic. Scenario
manifests are in format 4, which holds a house as an installation, and
checkpoints in format 4, which keeps a run's plan; manifests in formats 1
to 3, and checkpoints in formats 2 and 3, are still read, and every
checkpoint's identifier changes. The reference greenhouse's and the
tomato compartment's runs have new identities, their posts off the pipe
rails (#302); every other run keeps its own. The protocol's records for
acting are new and additive; its older action and execution names are
deprecated, and still read.

- `greenhouse-sim`: a playback is its run's gateway (P13.3, decision
  0046). It holds its run's plans in the protocol's reference gateway, on
  its clock, with the run as the executor (`services.gateway`). An action
  joins the run's plan as soon as it is given, its records are worked out
  again from its moment, and its outcome is written as the clock passes
  it. The run refuses what it cannot carry out when it falls due. A
  restart cancels what is pending, as the new epoch's first outcomes, and
  a run played to its end cancels what is left. The targets route is the
  local operator's plan, with its checks and messages as before. The
  consumer interface serves the outcome log:
  `GET /consumer/v1/runs/{run_id}/outcomes`.
- `greenhouse-protocol`: the reference gateway acts through any executor
  on its clock (`ClockedExecutor`), names it (`executor_ref`), and takes
  plans again when it is started over after it finished. It knows a run's
  controller targets from its items, as its devices and plants: given
  items without targets, it refuses a `set_target` as acting on what the
  run has not.
- `greenhouse-sim` and the viewer: the builder's zones and fixtures placed
  one by one (P12.3). The simulator's item edits take service zones,
  keep-out volumes, walkways, boxes, cylinders, pipes, pipe runs, rails and
  trays as they take equipment and sensors: placed several at a step,
  copied, spaced, given a value for a field and removed, `place_items`
  taking any of them. A zone or a walkway lies on the floor, so a step
  moves it along the floor only; a new fixture is named apart from the
  pipes or tubes a pipe run or a rail names after itself. The builder's
  palette places each of them, its list shows them, and its inspector
  shows their fields, the ends of a zone's area among them (it follows a
  model two objects deep, leaving out a rotation's quaternion). A pipe or
  a tube clicked in the view chooses its run or its rail.
- viewer and `greenhouse-sim`: the builder's inspector (P12.3). Every
  field of the item chosen, a nested one by its path, and the house's
  envelope and rows, read from the schema the simulator publishes, each
  value changed one edit the simulator makes and checks, undone in one
  step: an item's by `set_field`, the house's by the new `set_value` edit,
  which sets any field of an installation by its path (a list's item by
  its place, `envelope.openings.0.opening`). An item clicked in the view
  is chosen, the one chosen is drawn selected, and the items an error
  names are outlined on the house.
- `greenhouse-sim`: a run carries out a plan (P13.2, decision 0046).
  `RunRequest.plan` holds the protocol's `set_level` and `set_target`
  actions, each at a moment of the run or every day. The address's
  `&schedule=`, `&daily=` and `&targets=` are read into it as written,
  and the run checks it as before. Where a run starts from (`&set=`,
  `&open=`) stays the request's, beside its plan. Every run id, replay
  digest and kept opening day is unchanged. Checkpoints are written in
  format 4, which keeps the run's plan. Formats 3 and 2 are read as it,
  the kept opening days among them; an uploaded checkpoint's plan is
  refused, by the field at fault, if it breaks the protocol's rules. A
  checkpoint's identifier, a digest of its content, changes with the
  format, the kept opening days' too. Its summary is unchanged.
- viewer: the builder's equipment, sensors, doors and vents (P12.3). They
  are listed with their kind and place, and chosen many at once to be
  copied at a step, spaced evenly, given one value for a field, or
  removed. A palette places fans, heaters, dehumidifiers and sensors
  several at a step, and doors and vents on the walls or roof slopes
  chosen, at a step or spread evenly along each, the surfaces read from
  the house the simulator draws. Each is one edit the simulator makes
  (`POST /api/builder/edit`) and is undone in one step; an edit answered
  once the draft has changed is dropped, so that no edit is lost.
- `greenhouse-sim` and the viewer: `POST /api/builder/edit` makes an edit
  of many items (P12.3) on an installation's file, the body's `file`, and
  answers the installation it makes, assessed. The edit, the body's
  `edit`, is one of `builder.items`'s, told apart by its `edit`
  (`place_items`, `repeat_items`, `space_items`, `place_openings`,
  `spread_openings`, `repeat_openings`, `space_openings`, `set_field`,
  `remove_items`), and its JSON Schema is published as
  `builder/edit.schema.json`, from which the viewer's types are generated.
  A body that is no edit is refused by its fields, and an edit the
  installation refuses with the reason.
- `greenhouse-sim`: equipment, sensors, doors and vents edited many at a
  time (P12.3, `builder.items`). Pieces of equipment or sensors are placed
  several at a step, copied, or spaced evenly along an axis; doors and
  vents are placed at a step or spread evenly along each surface chosen,
  such as a row of vents along each roof slope, copied and spaced; one
  field, nested ones by their path, is changed over the items chosen; and
  items are removed. Each edit checks everything it changes, and the
  installation it makes as a file of it is read, before changing
  anything, and names new items after what they copy, with the lowest
  numbers free. An installation's assessment finds a heater or a
  dehumidifier through another or through a row's supports
  (`items_collide`), by the boxes themselves rather than the boxes around
  them, testing only pairs whose boxes along the house's axes meet, and
  doors or vents overlapping on a surface (`openings_overlap`). An
  installation whose layout names an item as a door or vent is named is
  refused.
- `greenhouse-sim`: the local API's routes are a module for each area of
  what it answers (`greenhouse_sim.api.routes`: `system`, `scenarios`,
  `runs`, `checkpoints`, `playback`, `live`, `lab` and `builder`), each
  with the table of its routes at its top, and what they share apart
  (AUDIT.17). `respond`, `live_stream` and `control` are imported as
  before, and every route answers as it did.
- `greenhouse-sim` and the viewer: a scenario's house as the builder's
  start (P12.2). `GET /api/scenarios/{id}/installation` answers a
  scenario's house as an installation, assessed, as its manifest holds it
  with its layout written out (`scenarios.installation.scenario_installation`);
  the builder copies it under an identifier of its own, so that the
  scenario itself is never changed. A scenario planting fewer positions
  than its layout's rows hold is refused, since its copy would plant them
  all; the builder takes only an identifier the simulator does, and says
  why when the scenarios cannot be listed.
- viewer: the setup builder, `/builder` (P12.2). A house is drafted from
  the first form, which reads its fields from the simulator's published
  schema, opened from the drafts or imported from a file; its rows are
  given a crop many at a time, each edit undone and redone in one step,
  by button or Ctrl/⌘+Z, with what stops it running shown as it changes
  and the house drawn as the simulator draws it. A draft is saved revision
  by revision, exported as a file, and a saved revision run as a scenario
  of its own, which the viewer opens. The browser tests' simulator keeps
  its drafts in a file of the run's own.
- `greenhouse-sim`: what the setup builder asks of the API besides its
  drafts (P12.2): `POST /api/builder/basic` makes a first draft from its
  first form's values, `POST /api/builder/assess` reads and assesses an
  installation's file as it is being edited, and `POST /api/builder/scene`
  draws the house it describes, as a scene, to preview it. The first two
  answer with the installation, the format a file of it is written in and
  its findings, so that an editor sends back what it is given; a draft's
  answer is the same, with a `draft` naming the draft and the revision, so
  that one published schema (`services/builder.schema.json`) describes an
  installation once. A form or a file refused, there or as a draft is saved, names
  every field at fault in its answer's `problems`, as the form or the file
  names it: the form checks what the envelope and the rows would refuse,
  such as a ridge below the eaves, before either is made.
- `greenhouse-sim`: the API keeps the installations' drafts and runs them
  (P12.1): `GET /api/drafts`, `GET /api/drafts/{id}` with what stops it
  running, its `revisions`, and `POST` to `save` an installation's file,
  `revert` and `delete`, a change on a stale revision answered `409
  Conflict`. `POST /api/drafts/{id}/run` registers a draft at a revision
  as a scenario of its own, with a period, a site, a seed and a weather,
  which is then listed, drawn and run as any scenario is; a draft with
  errors is refused with each. A draft is answered as the builder answers
  an installation, assessed, with the draft and revision it is under
  `draft`, its schema published once. The server keeps drafts in
  `~/.greenhouse-sim/drafts.sqlite3` unless `--drafts` names another file;
  where that default cannot be made, it starts keeping none.
- `greenhouse-protocol`: one format for acting on a greenhouse (decision
  0046, P13.1), as records, their checks and their published JSON Schemas
  (`greenhouse_protocol/schemas/`). New modules, all additive:
  - `actions`: `Action`, a union by `kind` (`set_level`, `set_target`,
    `water`, `harvest`, `lower`, `remove_leaf`, `inspect`), the protocol's
    own `ActionId`, and `ActionRef` for an occurrence or a fallback;
  - `plan`: `Plan` and `PlannedAction`, with timing (`At`, `Window`,
    `Asap`), `Recurrence`, `Lateness` (`on_late`: run late, skip, critical,
    fallback, abort the plan), `Principal`, `ExecutorRef`, `ActionKey` and
    `ActionState`; a malformed plan (an id twice, a prerequisite missing, a
    cycle, an edge between recurrences that do not pair) is refused whole;
  - `authorisation`: `AuthorisationConfig`, versioned, its groups granting
    action kinds, optionally on targets, delegation and managing plans;
  - `outcome`: `ActionOutcome`, whose fields agree with its status, and its
    typed `ActionEffect`;
  - `assignment`: `Assignment` and `ExecutionReport`, between a gateway and
    an executor;
  - `run`: `RunEpoch`; the consumer interface's `RunDescriptor` gains
    `continues_from`, left out of its JSON when unset.

  Deprecated, unchanged until the simulator carries the new format out:
  `greenhouse_protocol.action` (`RequestedAction`, `ActionResult` and the
  four request types) becomes `actions.Action` in a `plan.Plan`; the
  `ActionOutcome` and `ExecutionStatus` of `execution` become
  `outcome.ActionOutcome` and `OutcomeStatus`; `ActionExecutionAdapter`
  becomes a run's gateway and its executors (P13.1's contracts).
  `MAX_WATER_AMOUNT_ML` moves to `actions`, and `action` re-exports it.
- `greenhouse-protocol`: the contracts for acting on a greenhouse (decision
  0046, P13.1): `contracts.gateway.RunGateway`, a run's gateway, with its
  `/actuation/v1` routes, `Receipt`, `PlanState`, `GatewayLimits` and
  `occurrences`/`check_limits`; `contracts.execution.ActionExecutor`, with
  `Revocation` and `AssignmentStatus`; the consumer interface's outcome log
  (`OutcomeBatch` at `/consumer/v1/runs/{run_id}/outcomes`), held by
  `check_batch` and `check_polls` with `check_outcomes`, one outcome for
  each action however the log is paged. `check_gateway` and
  `check_executor` (with an action of a kind the executor carries out)
  hold an implementation to the contracts' rules, and
  `contracts.memory_gateway` is an in-memory reference implementation of
  both, which passes them, with faults to inject. The schemas of the
  receipt, plan state, limits and outcome batch are published beside the
  records'.

- `greenhouse-sim`: drafts of installations and their revisions are kept
  locally (P12.1, decision 0051): `greenhouse_sim.builder.drafts.DraftStore`
  keeps them in one SQLite file, each revision its installation's file. A
  draft is saved revision by revision, reopened at any, reverted to an
  earlier one (saved again as the latest) and deleted. A change names the
  revision it was made on and is refused if another was saved since, as by
  another window of the editor.
- `greenhouse-sim`: a scenario's manifest holds its house as an
  installation (P12.1, decision 0050). Manifest format 4 writes its
  envelope, its layout's name and the crop each row grows under
  `installation`, in place of format 3's `envelope`, `layout`, `rows`,
  `columns`, `crop_model` and `variety`; its rows and columns are its
  layout's crop rows and their planting positions. A format 3 manifest is
  migrated to it, and refused if its rows and columns are not its layout's.
  A manifest holding an installation a run cannot grow, with a row without
  a crop or rows of different crops, is refused saying so. The model is
  `greenhouse_sim.scenarios.installation.Installation`, which the builder
  imports (its `InstallationDraft` before), and an installation's file in
  format 3 or 4 is read. The packaged manifests are written in format 4:
  every run id and replay digest is unchanged. Each manifest's version, the
  digest of its content, is new, so a checkpoint saved before is refused as
  one of another version of its scenario, and the reference greenhouse's
  kept opening day was written again, changed in that digest alone.
- `greenhouse-sim`: each simulator keeps what it keeps, its climate runs,
  crops, sunlight, checkpoints and kept states, in stores of its own, made
  with it and forgotten with it (`Simulator.forget`, decision 0048): no
  store, lock or thread is made as a module is imported, and a test
  holds that. `stores.forget_everything` is gone. A scenario registered
  with a simulator now runs there as a packaged one does.
- `greenhouse-sim`: a scenario is looked up in the catalogue of the
  simulator answering (decision 0048): the services that look scenarios up
  take it, and a scenario registered with one simulator is listed and run
  by that one alone. Versions, opening days and layouts come from the
  catalogue's entries rather than from the manifests' files.
  `SCENARIO_REGISTRY` is read-only now, the packaged scenarios as
  `catalogue.PACKAGED` holds them.
- `greenhouse-sim`: `greenhouse_sim.builder`, the setup builder's first step
  (P12.0, decision 0050). An installation, the house part of a scenario
  (its envelope, its layout and the crop each row grows), is drafted from a
  form's values, assessed for what stops it running (each finding naming
  the items and rows it concerns), given a crop over many rows at once, and
  exchanged as a file in the manifests' format version, with its JSON
  Schema, `builder/installation.schema.json`. A refused file names each
  field at fault. Nothing in the packaged scenarios changes.
- `greenhouse-sim`: a layout's crop rows are bounded, as an envelope's spans
  and bays are: at most 1,000 rows, 10,000 positions a row and 100,000
  positions in all, and a run of pipes at most 1,000 pipes, so that a small
  file cannot ask for a crop too large to lay out. A row's support shorter
  than its two end legs stands on one leg, at its middle, where laying it
  out divided by zero.
- `greenhouse-sim`: every service that reads or keeps runs takes the
  simulator it keeps them in, and reaches its climate runs, crops,
  sunlight, checkpoints and kept states through it; so does a playback,
  which works its days out in its simulator's (decision 0048). The stores
  are still the services' modules', every simulator's, until each
  simulator makes its own.
- `greenhouse-sim`: the runs played back and the cursors given to
  consumers are a simulator's own (decision 0048): the API's server makes
  its simulator, answers every request from it and closes it as it closes.
  A playback stopped leaves the day it is working out at its next moment,
  rather than finishing the day, so the API stopped with a run playing
  back exits at once rather than after the day (some ten seconds for the
  reference greenhouse).
- Viewer: rows keep their place while a run plays: the climate run's
  loading line keeps its slot, and the View panel's Simulator row one line
  (#301). A checkpoint is uploaded by a button of the viewer's own, in its
  words whatever the browser's language (#303). Each side's panels fold to
  a stripe at the view's edge, kept folded in this browser, and the info
  panel's column is as wide as its widest panel (#304). The info panel's
  sections sit in titled cards by topic: Simulation, House, Equipment,
  Outside (#306).
- `greenhouse-sim`: an envelope may name the gutter lines that keep a post
  on its inner frames (`inner_posts`). A lattice girder under the gutters
  then carries the gutters between, from post to post, drawn and shading
  the sun like the other members. The reference greenhouse's posts inside
  the house now stand at the side walls only, and the tomato compartment's
  leave its middle path, so that no post stands on a pipe rail between the
  rows (#302). Both scenarios' runs have new identities, and the reference
  greenhouse's kept opening day, replay and QA views were worked out again.
  Every other scenario and its runs are unchanged.
- Viewer and `greenhouse-sim`: moves applied to equipment keep the run's
  heating target changes. A playback started over with another layout
  keeps them, each at its moment, and lists them in its state; the viewer
  keeps `&targets=` in the address, followed or not. A restart with the
  layout it plays drops them as before (decision 0049). The Move panel
  says in a line what applying the moves does, the details folded under
  "How moving works", and "Start a new run with these moves" asks first,
  in the panel: "Start the new run" applies them, "Back to the moves" or
  Escape returns to them (#305).
- `greenhouse-sim`: the packaged scenarios are read once into an
  unchanging catalogue (`scenarios.catalogue.PACKAGED`), each with its
  manifest's digest, opening day and layouts; a catalogue of one's own
  (`Catalogue`) registers other scenarios beside them, never in their
  place. `SCENARIO_REGISTRY` holds the packaged scenarios as before. The
  first step of one `Simulator` object owning the simulator's state
  (decision 0048, AUDIT.15).
- `greenhouse-sim`: the services log, at INFO, each run and value they
  make (with how long it took and how many kept ones it was made from),
  keep, take over from a checkpoint's kept states, and let go (past their
  bound, dropped, or forgotten), each named by its scenario and a digest of
  what tells it apart (AUDIT.14). As a library the package prints nothing
  until an application configures logging; the local API does, at INFO for
  the simulator, beside each request's line.
- Releases: a release is a pull request from a `build/release-<version>`
  branch that the repository's owner merges, opened by the owner or a
  release manager listed in `.github/release-managers`. The owner then tags
  its merge commit with `uv run release tag <pull request>`, and the tag's
  push runs the `Release` workflow, which publishes the GitHub release with
  the changelog's section (decision 0045). Both check the release first.
  `uv run release prepare <version>` moves the three packages, the
  protocol's range and the changelog to the version and locks; `uv run
  release video <url>` points the README's demo at an uploaded video. The
  release skill (`.claude/skills/release/SKILL.md`) walks through it.
- `uv run record-demo` cuts the walk-through's recording for the README:
  from the moment the walk-through's opening shot, the house and its crop,
  is drawn, at twice the speed, as an MP4 under GitHub's upload limit, with
  its first frame saved beside it to check. It needs ffmpeg. The
  walk-through lingers 3 s on each caption.
- `greenhouse-sim`: the list of a scenario's fields
  (`GET /api/scenarios/{id}/fields`) is published as a JSON Schema too
  (`services/field_names.schema.json`), the last of the API's answers the
  viewer read by hand (W12). The viewer reads it by its schema, and lists
  no fields from an answer that does not fit, as it did from one it could
  not read. The answer itself is unchanged.

## 0.3.0 - 2026-10-21

The reference greenhouse's run played back against one clock, which the
viewer and a consumer follow (P10), under a season, with a thermostat on
its heater; the consumer interface in the protocol; and the climate
controller's first steps (P11): the controller as data, and heating
targets changed from a moment on, from the viewer or through the
simulator's API. Every run's identity changes, and scenario manifests and
checkpoints are in format 3; manifests in formats 1 and 2, and format 2
checkpoints, are still read.

- The viewer follows a scenario's own run as it is played back (#245):
  its moment moves with the playback's clock, its own play and sliders
  stand aside while it follows (#270), and a "Heating targets" section sets
  the run's heating setpoints from the moment drawn, or the run played
  back's from its next minute (#274). Every group of its info panel folds
  to a line that says how it stands (#273), the controls list each action
  once (#272), and the crop stays drawn under the sun, its geometries
  disposed once nothing draws them (#269).
- `greenhouse-sim`: every answer of the API that the viewer reads is
  published as a JSON Schema beside the service that gives it
  (`greenhouse_sim/services/*.schema.json` and its kin, W12), and the viewer
  reads each answer by its schema, refusing one that does not fit.
- `greenhouse-sim`: the API reads the run a request asks for once, for
  every route that makes or keeps one (W11): the timeline, which ignored
  `&open=` and `&weather=`, now refuses a malformed one as the others do.
- `greenhouse-sim`: a heater gives its heat to the air its outlet blows
  through, along its heading over its jet's core, weighted as a round jet's
  speed is, rather than to the few cells around its body (#261). In the
  reference greenhouse's first minutes its warmest cells were 102 to 108 °C
  and are now 50 to 55 °C, a unit heater's outlet. Its total heat is the
  same, and so is the house's air, which the run follows after its first
  two hours: the reference run's day 0 replay digest changes, and its later
  days and opening days do not. In a shut house the grid's mean now runs
  about half a degree above the whole house's, its heat kept from the cold
  glass.
- `greenhouse-sim`: a run's heating setpoints can change from a moment on
  (#274, decision 0043): `&targets=3600:heating_day:24` on every route that
  makes or keeps a run, its thermostat heating to the targets in force,
  each change part of the run. A playback's run is steered while it plays
  by `POST .../playback/targets?targets=heating_day:24`, from its clock's
  next minute, in the same run and epoch; its state lists the changes. The
  equipment route gives the thermostat's setpoints by day and by night.
  Checkpoints are in format 3, keeping a run's target changes; format 2 is
  read as one that made none, and the opening days are written again in
  format 3. Runs that change no target keep their identity.
- `greenhouse-sim`: scenario manifests are in format 3 (P11.1). A
  scenario's `thermostat` is now the heating loop of its climate
  controller, `control`, which holds its loops, their targets, bands and
  stages, and checks them (`climate.control`): heating, venting in stages,
  circulation and dehumidifying, a dead band kept between heating and
  venting. A scenario runs its heating loop alone until the house decides
  every loop (P11.2); the others are refused until then. Manifests in
  formats 1 and 2 are migrated as they are read. The runs do not change,
  but every run's identity does, since it covers the scenario's whole
  configuration: the reference run's id, and the digests of its manifest
  kept beside its opening days and its replay, are written again.
- `greenhouse-sim`: a playback plays its scenario's own layout or one
  rearranged (#271, decision 0041). `POST .../playback/restart?layout=`
  starts it over with that layout's run from its first day, a new run with
  its own identity and epochs, and `start` takes a layout too; its state
  says the layout it plays. A consumer finds the new run in its list of
  runs. The viewer's Move panel holds moves as a draft: equipment and
  sensors dragged stay where they are dropped, and "Start a new run with
  these moves" applies them all at once from the run's start, starting the
  run played back over with them while the view follows it.
- `greenhouse-sim`: the climate's 3D air takes steps up to 0.9 of the
  longest that keeps each new temperature a weighted mean of the old ones,
  not half of it: a late day of the reference greenhouse draws its air in
  1.3 s, not 2.2, and a day step costs about 4.3 s, not 5.2 (#198). The
  air drawn moves by 0.02 K at most. The sensors read the grid only through
  a run's first two hours, the house's air after: there, a few readings
  move by one step of their rounding (20 of the reference run's 2,341 in
  its first three hours, by 0.1), and none after. The reference QA page's
  kept views are written again.
- `greenhouse-sim`: air past water's boiling point holds any water, and
  none condenses from it. A cell the heater warmed past 100 °C used to lose
  more water than it held, as the saturation ratio's formula turns
  negative there: in the reference greenhouse's first minutes the house's
  humidity cell by cell ran to ±10⁸ %, and its hygrometers, which read the
  grid run through a run's first two hours, read 0% and then 100% for over
  an hour. They now read 43 to 89%. The reference run's day 0 replay digest
  changes with them; days 1 and 2, read from the house's air, do not.
- `greenhouse-sim`: the reference greenhouse's back temperature sensor
  drifts 0.001 °C an hour, not 0.01. Its drift grows from the run's start,
  and over the 120-day season 0.01 added 29 °C, so it read 42 to 58 °C in
  June; now it reads about 2 °C high by the opening day, still a fault a
  consumer can find. The run's identity changes with it.
- `greenhouse-protocol`: the consumer interface
  (`greenhouse_protocol.contracts.consumer`, decision 0040, P10.1): how a
  client reads a running producer, whatever it is. Routes under
  `/consumer/v1` answer a run's identity, epoch and clock, its greenhouse
  description, and its observations and events after a cursor, in delivery
  order, with nothing from after the run's clock. `check_batch` and
  `check_polls` hold a producer to the rules, and a recorded exchange
  (`tests/fixtures/consumer/exchange.json`) lets a client be built before
  any producer serves it.
- `greenhouse-sim`: a scenario's own run played back against one clock
  (decision 0041), which the viewer and a consumer follow: its point
  sensors' readings worked out ahead, day by day, at a consumer's cadence
  of 300 s, and served only as far as the clock has reached; the run's
  identity, epoch and instant said the same way to both. The API starts,
  plays, pauses, restarts and paces it (`/api/scenarios/{id}/playback`).
- `greenhouse-sim`: the consumer interface served from a played-back run
  (P10.4): `GET /consumer/v1/runs`, a run, its greenhouse, and its
  observations and events after a cursor, on the API's loopback server;
  observed records only. Besides the sensors' readings, the run's
  organ-level crop delivers a daily walk through it at noon (each plant's
  fruit and red fruit counted, their mass estimated, its height measured,
  with the scenario's observation errors) and its weekly harvests, one
  `HARVEST` event per plant picked. `uv run api --play reference_greenhouse
  [--hold]` starts the run with the API, held until told to play if asked.
- `greenhouse-sim`: a season and a thermostat (P10.3, decision 0042). A
  scenario's weather can follow the year (`"kind": "seasonal"`): each day's
  coldest and warmest temperatures go from winter's to summer's and wander
  in spells drawn from the seed, each day its own clouds. A thermostat runs
  a heater by the house's air, on below its setpoint by half its band and
  off above it by as much, a setpoint by day and one by night; a command to
  the heater takes it over. The heat a run's heaters give is counted, and
  played back hour by hour as `HEATING_ENERGY_INCREMENT_MJ_M2`, modelled
  heat input per square metre of floor, not a meter's reading. The viewer draws
  and says the thermostat's heater as the run has it
  (`GET /api/scenarios/{id}/climate/equipment`). A run's identity now covers
  everything its scenario is made of, so a changed manifest or layout is
  another run.
- `greenhouse-sim`: the reference greenhouse under a season from 1 March
  and its heater, now 30 kW, on a thermostat at 18 °C by day and 16 °C by
  night, in place of the cold spring day every day and the heater by the
  clock. Its run is another: its identity, its opening day and its numbers
  change.
- `greenhouse-sim`: the identifier of a piece of equipment
  (`actuator_id`), a sensor (`sensor_id`) or a door or vent (`opening_id`)
  holds only letters, digits, `_`, `.` and `-`, as `layout.schema.json` and
  `scenario.schema.json` now say. The API's parameters write identifiers
  between `:` and `,`, so an item named otherwise could not be set,
  scheduled or moved; a layout or scenario that names one is now refused
  as it is read. Scenario manifests are in format 2 for it
  (`schema_version`, decision 0031); a format 1 manifest is read as format
  2, and refused only if it names an item otherwise.

## 0.2.0 - 2026-10-19

The simulator's greenhouse, crop, air, sensors and sun, the reference
scenario's season, and the browser viewer that draws them (P00 to P09).
Several entries break 0.1.0's interfaces: the Python floor, records'
timestamps, a description's tuples, and worlds serialized by 0.1.0.

- All three packages now require Python 3.14 or newer (previously 3.12).
- `greenhouse-protocol`: every record's timestamps are timezone-aware, checked
  as a record is built (`greenhouse_protocol.instant.Instant`): an
  observation, event, frame or greenhouse description with a naive time is
  refused, as a capture already was. An observation's quality is written in
  order, so its bytes do not depend on the process. `check_media` refuses a
  capture that names no greenhouse.
- `greenhouse-protocol`: a greenhouse description, an action and an outcome
  check every edit as they were checked when built, and a refused edit
  leaves them as they were. A description's plants, compartments and layout
  are frozen, and its `plants`, `compartments` and `all_plants`, and a
  compartment's `plants`, are tuples: a plant or compartment is added or
  changed by assigning the description's field, which checks its identity.
- `greenhouse-sim`: the simple tomato model's own values (a plant's growth
  multiplier and water stress; a fruit's target diameter, growth-rate
  multiplier and ripening day) move from `PlantWorld` and `Fruit` to
  `GreenhouseWorld.plant_model`. Worlds serialized by earlier versions no
  longer load.
- `greenhouse-sim`: `ScenarioConfig` refuses values no run can have:
  `rows`, `columns`, `duration_days`, `truss_interval_days`,
  `fruit_growth_days_to_target` and `water_capacity_ml` are positive, and
  `random_seed` and `max_trusses` are not negative. Such values used to be
  accepted, and some then failed deep in a run.
- `greenhouse-sim`: plant, environment and sensor models plug into
  `SimulationEngine` through contracts (`PlantModel`, `EnvironmentModel`,
  `SensorModel`), with the existing dynamics kept as the default simple
  models. The internal modules are regrouped by domain; the public import
  paths are unchanged and now documented.
- `greenhouse-sim`: `scene_snapshot` describes a world as a renderable scene,
  in metres with z up.
- `greenhouse-sim`: a local API for the browser viewer
  (`python -m greenhouse_sim.api`), using only the standard library. It
  refuses a body over 64 MB, one that does not arrive in full, or one
  holding `NaN` or `Infinity`, and answers `PUT`, `PATCH` and `DELETE`
  with 405.
- A browser viewer for the simulator in `greenhouse_sim/web`, outside the
  Python package.
- `greenhouse-sim`: a greenhouse as data (P01, P02): its envelope, spans and
  bays, glazing, doors and vents, and its layout of rows, gutters, rails,
  benches, equipment and sensors, read from JSON files and checked.
- `greenhouse-sim`: an organ-level tomato model (P03): stochastic
  development, procedural plant geometry, crop work (pruning, harvesting,
  lowering) and a plant lab.
- `greenhouse-sim`: the greenhouse's air (P04, P05, P07): environment fields
  on a grid, prescribed airflow and OpenFOAM's out of process, and a climate
  driven by fans, a heater, a dehumidifier and vents, under recorded,
  synthetic or constant weather, with the house's air as one volume through
  a run.
- `greenhouse-sim`: virtual sensors and cameras (P06), sampling at most
  once a second, with noise, bias, drift, latency and dropouts, an
  observation log and each sensor's freshness; and the sun (P08): its
  position, the glazing's transmission, shadows, and each plant's light.
- `greenhouse-sim`: the reference scenario and its season (P09): every
  scenario a versioned JSON manifest; the reference greenhouse's 32 plants
  grown organ by organ through 120 days in their run's air and their own
  light, on one clock, with a timeline; checkpoints, of which an upload
  is refused unless a run could reach it, branches and replay digests; a
  kept opening day; a QA mode with the truth and a developer panel; golden
  views; a benchmark (`python -m greenhouse_sim.benchmark`); and the
  API's `Server-Timing` header.
- The viewer draws all of it (P00 to P09), with screenshot regression in a
  pinned container, and `uv run demo` starts the API and the viewer
  together and opens the reference greenhouse (`docs/demo.md`).
- The viewer zooms towards the point under the pointer and stops at the
  camera's closest approach, hides the overlays over the scene apart from
  the run, folds a run's daily schedule to a summary, and gives up the
  requests it no longer needs.
- A clone is a uv workspace: `uv run <command>` installs Python 3.14 and
  the packages and runs a task, `uv run setup` installs the viewer's
  packages, Chromium and the git hooks, and `uv run help` lists the rest
  (`demo`, `start`, `api`, `viewer`, `check`, `viewer-checks`,
  `browser-tests`, `record-demo`; decision 0039).
- `greenhouse-adapters`: a verified artifact is hashed again once its size,
  inode or modification time changes, and after every fetch; a fetched
  file that fails its checksum is moved aside, so the next run fetches it
  again. A download the publisher answers with 429 or 5xx, or that the
  connection cuts short, is resumed up to four times, waiting longer each
  time, and its bytes are kept; a resume no longer empties the partial
  file on an error, and a short or long body never reaches the final path.
- `greenhouse-adapters`: `greenhouse-data` ends a checksum mismatch, a
  network error or an archive that is not one in a line and exit code 1,
  instead of a traceback.
- `greenhouse-adapters`: a canonical build writes only records that pass
  the protocol's checks, and otherwise raises `RefusedBuild`, naming the
  first violations. It dates a greenhouse by its first reading rather than
  by when the build ran, and refuses a source with no readings.
- `greenhouse-adapters`: `excel_serial_to_utc` refuses a local time that
  the clocks skip or repeat, as `matlab_datenum_to_utc` already did.
- `greenhouse-adapters`: an artifact's name is a plain file name, with no
  folder, `..` or `:`; manifests and the canonical tier are read and
  written as UTF-8; and `greenhouse-data inventory --write` refuses to
  overwrite an installed package's manifests.
- All three packages now require pydantic 2.12.2 or newer (previously 2.9):
  `Observation` leaves its unset fields out with `exclude_if`, which
  pydantic 2.11 ignores, and 2.12.0 fails on Python 3.14. CI installs the
  protocol and the adapters at their lowest dependencies and tests them.

## 0.1.0 - 2026-09-24

First public release.

- `greenhouse-protocol`: canonical records, record store and query
  contracts with an inclusive `up_to` boundary, the action-execution
  contract, conformance checks, and an in-memory reference store.
- `greenhouse-sim`: deterministic simulator with a hidden world, noisy
  sensors, semantic actions through a pluggable executor, three scenarios,
  and ground truth behind an evaluation-only interface.
- `greenhouse-adapters`: dataset manifests, checksummed and resumable
  artifact resolution with download caps per profile, the deterministic
  canonical tier, adapters for the WUR Autonomous Greenhouse Challenge 2023
  pre-trial and 2024 challenge datasets, and the `greenhouse-data` command.
