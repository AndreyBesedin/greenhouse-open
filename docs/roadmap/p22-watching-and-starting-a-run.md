# P22: Watching and starting a run

**Status:** proposed, in progress (P22.1 and P22.2 are done). What the [QA of 2026-11-04](qa-2026-11-04.md)
planned beyond its fixes. Part of the [simulator roadmap](README.md).

## Goal

A person starts a run from one form that says what it will compute, and watches
it in one place, the replay, with one *Play*. They can tell what each control
does, what "s a day" means, and why the view is where it is.

## Where it starts

The walk of 2026-11-04 found the viewer working, and hard to find one's way in:

- **Two ways to watch a run.** *Replay* and *Follow* differ in no way a person can
  tell. *Follow* is `FollowLink` in `greenhouse_sim/web/src/landing/RunParts.tsx`,
  and the viewer's own play is `src/PlaybackPanel.tsx`, `src/scene/useFollow.ts`
  and `src/plan/useSteering.ts`, wired in `src/App.tsx`. The walk liked the
  replay's panel under the view best.
- **Steering lives in the viewer's play only.** The server takes a change to a
  running epoch (`POST /api/runs/{run}/epochs/{n}/changes`,
  `greenhouse_sim/greenhouse_sim/api/routes/stored.py`), and the viewer never
  calls it: a replay's panels only fork
  ([P17.8](archive/p17-runs-and-playbacks.md), "not delivered").
- **A new run asks two things.** A scenario's dialog
  (`src/landing/RunsDialog.tsx`) leads with *Open in the viewer*, whose purpose
  was not clear, and starts a run from a seed and a pace. Starting a run takes
  only `seed`, `layout` and `seconds_per_day`.
- **The scene falls behind at speed** (D3). At 10 s a day the timeline reads
  Day 15 while the panels read Day 13, each load taking 4 to 6 s: the replay
  moves its moment only once the climate field for the last one has arrived
  (`src/scene/useReplayMoment.ts`), and the sun, so the shadows, follow that
  moment.
- **The panels say more than they need.** With a run open, the header reads
  "greenhouse-sim viewer" with a commit; display options sit under the
  scenario's chooser; equipment reads by identifier; the panel under the view
  does not fold, and its buttons say nothing on hover.

## What stays stable

- A run's identity, its records and its replay digests: this project changes how
  a run is shown and started, not what it computes.
- The playback routes and the policy's port ([P15](archive/p15-policy-port.md)), until a
  decision of this project says what becomes of them.
- The design system's rules ([P19](p19-design-system.md)): new controls are its
  components, and a change of look is one of its named visual changes.

## Steps

| Step | Work | Accepted when | Status |
| --- | --- | --- | --- |
| P22.1 | **Steer a running epoch from the replay:** a target or a command changed in a replay's panels, while its epoch runs, posts to the epoch's changes and reads them back, in place of a fork | A change made in a replay steers the running epoch, from its moment, and a finished epoch still forks | Done ([decision 0073](../decisions/0073-a-change-in-a-replay-steers-a-running-epoch-at-its-own-clock.md)): while the replay's position says its epoch is `queued` or `running`, a heating target set in its panels, or a level of a piece of equipment, a door or a vent, is asked of the epoch (`POST /api/runs/{run}/epochs/{n}/changes`) and nothing forks; once it says the epoch has ended, a change is a fork from the moment shown, as before, and moves applied are a fork either way. The change takes at the epoch's own clock as its worker takes it (a target from the next minute, a level from that moment), not at the moment shown, which is at or before the frontier while the worker is past it; the panels say so before it is made. The replay reads the epoch's changes (`GET …/changes`) every second until the worker is done with the request (`done`, which a worker writes after its answer, since it logs a change before it acts on it and may refuse it then), and then names the moment it took effect from, or says in words why it was refused, by the route (an epoch that ended before it was asked) or by the worker, or that the epoch ended before its worker took it; none of these is made a fork, and what became of a change is still said once the epoch has ended. A level set waits beside the reading, "set to 100%", until the replay reaches the moment it takes; the panels show a change from its moment once a commit passes it, from the plan the position reads (P17.8). One steering path for the panels (`plan/useSteering.ts`), given how actions reach the run: the viewer's own play through its plan, or a running epoch through its changes (`replay/changes.ts`). The answers of `…/changes` are published (`change_asked.schema.json`, `epoch_changes.schema.json`) and the viewer's side generated from them. Not delivered: a change at a past moment of a running epoch, which is a fork from the header and then a change in it, at the fork's own clock; a plant's work, which only the viewer's own play offers; the browser specs that set a level in a replay now stop its run first, to fork it |
| P22.2 | **One *Play*:** *Follow* goes; the replay follows a run that is computing | Every list of runs offers one way to watch each | Done: the start page's list of runs and a scenario's dialog have one link to watch each run, *Replay* (`ReplayLink`, `src/landing/RunParts.tsx`), and *Follow* is gone with its column. The link of a run queued or running opens its replay following the newest day computed (`&follow=1`, as a run just started from the dialog or the builder already did), and says so on hover; that of a run computed no longer opens at its start, as before. Followed, the replay stands at the frontier as it moves; *Play* from there, or from an earlier day, plays at the replay's pace and waits at the frontier while the run computes, moving on as days arrive (the position's own behaviour since P17.4, now held by a browser spec from the list). A replay that followed its epoch to the end no longer asks where its position stands every second after it, since the frontier of a finished epoch does not move; one that follows an epoch interrupted or failed still asks, since it may be resumed from elsewhere. Not delivered: the viewer's own play and its *Follow* of a scenario's run in the scenario list (`SourceChooser`), which are P22.3's; a fork still being computed opens following its frontier from a list too, not held at the moment it was made from as *Fork from here* opens it; the replay's *Follow the newest day* stays beside *Play*, as a way back to the frontier |
| P22.3 | **The viewer's own play goes,** with a decision on the playback routes and the policy's port | No control starts a playback in the viewer; the browser tests that used it watch in the replay | Proposed: [decision 0074](../decisions/0074-the-viewers-play-and-the-playbacks-http-surfaces-go.md) (proposed), in the [pull requests below](#p223s-pull-requests) |
| P22.4 | **A new run's form:** the dialog leads with starting a run and lists the runs under it; *Open in the viewer* goes. The form: what the scenario is, its duration, its weather, the crops to read, with a way to make a new scenario from this one (`src/builder/CopyScenario.tsx`), and how fast to compute it; the seed small and optional, as it is now. The start route takes the duration and the weather | A run is started with a duration and a weather of the form's, and repeated by its seed | In progress ([decision 0075](../decisions/0075-a-runs-weather-and-a-shorter-duration-are-its-own-as-its-seed-is.md), proposed): the start route takes `weather`, one of the scenario's by name, and `duration_days`, from 1 to the scenario's own, each its own when not given. A weather other than its own makes another run, as a seed does; fewer days are the same run ended sooner, its first days' digests the whole run's. The epoch keeps both, so that its worker, a resume and a fork run as it was started, and the runs listed and a position say its `weather`, under which the replay draws its scene. The runs dialog's form (`RunsDialog.tsx`) asks for them: its days, from 1 to the scenario's own, which it refuses otherwise before asking, and its weather, in words (`weatherName`), each its scenario's own until changed and asked for as none then; the scenario's crop in words, with *Make a new scenario from this one*, which opens the builder with the scenario chosen to copy (`/builder#copy=<id>`, `CopyScenario`); the pace; and the seed, small and optional, as before. Its fields are the design system's `Field`, its button `Button`, its link `LinkButton` and its problems `Notice`, the controls keeping the start page's look until P19.8. *Open in the viewer* is gone. `/view`'s own climate play stays: it starts no run and keeps nothing (decision 0074), and the builder's *Open in the viewer*, QA mode and links from before still reach it; whether it keeps a play of its own is left with P22.8, which reshapes the viewer's panels. Still to come: the dialog leading with the form, the runs listed under it, in place of *New run* |
| P22.5 | **The pace, said once:** a replay's "s a day" is how fast it shows; the form's is how fast the run computes, and each says so | Neither reads as the other | Proposed |
| P22.6 | **The scene keeps up** (D3): measured first, server cost per moment against the viewer's loads; then the replay skips moments or loads ahead (`useReplayMoment.ts`, `src/fields/useClimateLoads.ts`) | At 10 s a day, the panels and the timeline show the same day | Proposed |
| P22.7 | **The start page:** a title that says what the place is for, the two choices equal, one under the other with "or", each with an icon, fewer words and a tooltip on each button. Before P19.8, which moves the landing page's controls, or folded into it | The walk's words, read on the page | Proposed |
| P22.8 | **The viewer's panels,** three changes one after another: the header names a run or a simulation, with the version and not the commit except on a branch; a *Display* card beside *House*; equipment in groups, without identifiers. With P19.11 | Each read on the page | Proposed |
| P22.9 | **The panel under the view:** it folds as the side panels do, their arrows taking the panel's whole height or width; each button says what it does on hover, *Fork* first; *Delete* in place of *Other runs*. With P19.10 | Each read on the page | Proposed |
| P22.10 | **The QA scenario** below, run and recorded | Each step passes in the browser | Proposed |

P22.1 comes first: P22.2 and P22.3 take away the steering the viewer's play has,
and P22.4's *Open in the viewer* goes with P22.3. P22.5 to P22.9 are independent
of them and of each other, but for P22.7 to P22.9 lining up with P19's steps.

## P22.3's pull requests

As [decision 0074](../decisions/0074-the-viewers-play-and-the-playbacks-http-surfaces-go.md)
proposes them, each under about 500 lines but for generated files and files
deleted whole, in this order, so that no browser spec loses what it watches
before the code it watched goes:

1. **The decision and this plan** (`docs`).
2. **The specs that only needed a moving run watch a replay** (`test(viewer)`):
   `selection.spec.ts`, `info-panel.spec.ts`, `panels.spec.ts`'s #304,
   `renderer-smoke.spec.ts` and `p09-final-qa.spec.ts`'s 0.5.0 step, on a run
   asked of a worker and opened in its replay; and those of `follow.spec.ts`
   the replay does not hold yet (a moment whose field fails, a house without
   equipment) in `replay.spec.ts`. No code of the viewer changes.
3. **The plan lane in the replay** (`feat(viewer)`): read from the position's
   outcomes, in place of the consumer interface's and the gateway's;
   `plan-qa.spec.ts` gives its plans to a running epoch through its changes
   and reads them in its replay.
4. **A plant's work in the replay** (`feat(viewer)`): `PlantActions` for the
   selected organ's plant, each action a plan of its own asked of a running
   epoch through its changes (`changesFor` taking crop actions), or a fork's
   change from the moment shown once the epoch has ended; what became of it
   said beside the panels, as for a level, and in the plan lane; a test of
   `replay.spec.ts` for each.
5. **Moves leave the followed view** (`refactor(viewer)`): `useMoveSession`
   and `MovePanel` without a playback to start over, `PlantActions` no longer
   beside the playback's panel, and `moving.spec.ts`'s #271 test of a
   followed run.
6. **No *Follow*, and the old addresses mean nothing** (`feat(viewer)!`):
   `SourceChooser` and `ScenarioList` without *Follow*; the address no longer
   reads `?live=` or a scenario's `&follow=1`, so that a page opens as it
   would without them (`/?live=<id>` the start page, as `/` is), which a unit
   test of the addresses holds; `follow.spec.ts` goes, what of it the replay
   needs held by step 2. A replay's `&follow=1` stays. After it, nothing sets
   a scenario's `follow`.
7. **The followed view's code goes** (`refactor(viewer)`): `PlaybackPanel`,
   `useFollow`, `scene/playback.ts` and its generated contracts,
   `useFollowFraming`, `useGiveToPlayback` and what of `plan/plan.ts` only it
   used, the playback's words in `ClimateTime`, their unit tests, and the
   viewer's README. Nothing reaches them after step 6.
8. **The playbacks' HTTP surfaces go** (`feat(api)!`). First, a search for
   every use over HTTP of `/api/scenarios/{id}/playback`, `/consumer/v1`,
   `/actuation/v1` and `--play`, in the code, the tests, the examples, the
   documents and CI, each moved or gone. Then `api/routes/playback.py`,
   `api/consumer.py`, `api/actuation.py` and `services/actuation.py` go, with
   the `targets` alias, the server's `--play`, `--hold` and
   `--play-seconds-per-day`, `playback.schema.json`, `test_consumer_api.py`,
   `test_actuation_api.py` and the HTTP parts of `test_playback.py`,
   `test_plan_final_qa.py`, `test_failed_playback.py`, `test_route_table.py`
   and the others; the READMEs, the protocol's included, no longer say the
   simulator serves `/consumer/v1` or `/actuation/v1`.
9. **The simulator's book of its playbacks goes** (`refactor(sim)!`):
   `Playbacks`, `Simulator.playbacks` and the module's functions that read it
   (`playback.start`, `command` and their like), with what reads it: a
   position held behind a playback's clock, the epochs a playback holds, a stop
   or an authorisation reaching an epoch through its playback, and the
   consumer reads by a run's identifier. The port's server and examples 01 and
   02 make their own `Playback`, as the experiment's runner does; the tests
   that drove the book drive a `Playback`. `test_run_policy_port.py`,
   `test_policy_in_its_own_process.py`, `test_run_gateway.py`,
   `test_experiment.py` and the examples' tests still pass. With it, the items
   of [future work](future-work.md) P17 and P18 left to P22.3 are settled
   there, this step is done and the decision accepted.

*Open in the viewer*, in `src/landing/RunsDialog.tsx`, is P22.4's.

## QA scenario (proposed)

In the browser, on the reference greenhouse:

1. From the start page, start a run of 10 days, with another weather, from the
   scenario's form; its seed left empty.
2. Watch it compute in the replay, with one *Play*, at 10 s a day: the panels and
   the timeline read the same day throughout.
3. While it computes, raise the heating target by day from the replay's panels:
   the run steers from that moment, and nothing forks.
4. Fold the panel under the view and open it again; hover each of its buttons.
5. Delete the run from the replay, and land on the start page.
6. Start the same run again with the seed the first one used: the same run.

## Open questions

- **The playback routes and the policy's port.** The viewer's own play uses the
  playback routes, and P15's port reads live playbacks. Whether they stay for
  consumers, or a run's epochs take their place, is P22.3's decision:
  [decision 0074](../decisions/0074-the-viewers-play-and-the-playbacks-http-surfaces-go.md),
  proposed, takes the playbacks' HTTP surfaces away and keeps the port.
- **Duration and weather as a start's inputs:** whether they make another scenario
  or stay a run's, as its seed is: [decision 0075](../decisions/0075-a-runs-weather-and-a-shorter-duration-are-its-own-as-its-seed-is.md),
  proposed, keeps a weather and fewer days a run's, and a longer season a
  scenario of its own.
