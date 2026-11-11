# P22: Watching and starting a run

**Status:** done: P22.1 to P22.10, its QA run and recorded (P22.10); what it left is in
[future work](../future-work.md#watching-and-starting-a-run-after-p22). What the [QA of 2026-11-04](qa-2026-11-04.md)
planned beyond its fixes. Part of the [simulator roadmap](../README.md).

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
  ([P17.8](p17-runs-and-playbacks.md), "not delivered").
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
- The policy's port ([P15](p15-policy-port.md)), in the process and over its
  own server. The playback routes went in P22.3
  ([decision 0074](../../decisions/0074-the-viewers-play-and-the-playbacks-http-surfaces-go.md)).
- The design system's rules ([P19](p19-design-system.md)): new controls are its
  components, and a change of look is one of its named visual changes.

## Steps

| Step | Work | Accepted when | Status |
| --- | --- | --- | --- |
| P22.1 | **Steer a running epoch from the replay:** a target or a command changed in a replay's panels, while its epoch runs, posts to the epoch's changes and reads them back, in place of a fork | A change made in a replay steers the running epoch, from its moment, and a finished epoch still forks | Done ([decision 0073](../../decisions/0073-a-change-in-a-replay-steers-a-running-epoch-at-its-own-clock.md)): while the replay's position says its epoch is `queued` or `running`, a heating target set in its panels, or a level of a piece of equipment, a door or a vent, is asked of the epoch (`POST /api/runs/{run}/epochs/{n}/changes`) and nothing forks; once it says the epoch has ended, a change is a fork from the moment shown, as before, and moves applied are a fork either way. The change takes at the epoch's own clock as its worker takes it (a target from the next minute, a level from that moment), not at the moment shown, which is at or before the frontier while the worker is past it; the panels say so before it is made. The replay reads the epoch's changes (`GET …/changes`) every second until the worker is done with the request (`done`, which a worker writes after its answer, since it logs a change before it acts on it and may refuse it then), and then names the moment it took effect from, or says in words why it was refused, by the route (an epoch that ended before it was asked) or by the worker, or that the epoch ended before its worker took it; none of these is made a fork, and what became of a change is still said once the epoch has ended. A level set waits beside the reading, "set to 100%", until the replay reaches the moment it takes; the panels show a change from its moment once a commit passes it, from the plan the position reads (P17.8). One steering path for the panels (`plan/useSteering.ts`), given how actions reach the run: the viewer's own play through its plan, or a running epoch through its changes (`replay/changes.ts`). The answers of `…/changes` are published (`change_asked.schema.json`, `epoch_changes.schema.json`) and the viewer's side generated from them. Not delivered: a change at a past moment of a running epoch, which is a fork from the header and then a change in it, at the fork's own clock; a plant's work, which only the viewer's own play offers; the browser specs that set a level in a replay now stop its run first, to fork it |
| P22.2 | **One *Play*:** *Follow* goes; the replay follows a run that is computing | Every list of runs offers one way to watch each | Done: the start page's list of runs and a scenario's dialog have one link to watch each run, *Replay* (`ReplayLink`, `src/landing/RunParts.tsx`), and *Follow* is gone with its column. The link of a run queued or running opens its replay following the newest day computed (`&follow=1`, as a run just started from the dialog or the builder already did), and says so on hover; that of a run computed no longer opens at its start, as before. Followed, the replay stands at the frontier as it moves; *Play* from there, or from an earlier day, plays at the replay's pace and waits at the frontier while the run computes, moving on as days arrive (the position's own behaviour since P17.4, now held by a browser spec from the list). A replay that followed its epoch to the end no longer asks where its position stands every second after it, since the frontier of a finished epoch does not move; one that follows an epoch interrupted or failed still asks, since it may be resumed from elsewhere. Not delivered: the viewer's own play and its *Follow* of a scenario's run in the scenario list (`SourceChooser`), which are P22.3's; a fork still being computed opens following its frontier from a list too, not held at the moment it was made from as *Fork from here* opens it; the replay's *Follow the newest day* stays beside *Play*, as a way back to the frontier |
| P22.3 | **The viewer's own play goes,** with a decision on the playback routes and the policy's port | No control starts a playback in the viewer; the browser tests that used it watch in the replay | Done ([decision 0074](../../decisions/0074-the-viewers-play-and-the-playbacks-http-surfaces-go.md)), in the nine [pull requests below](#p223s-pull-requests). Steps 1 to 7 took the viewer's own play away, its specs watching in the replay. With step 8 the local API serves no playback: `/api/scenarios/{id}/playback` and its commands, the `targets` alias among them, `/consumer/v1`, `/actuation/v1`, the server's `--play`, `--hold` and `--play-seconds-per-day`, and `playback.schema.json` are gone. The tests that reached a playback over those routes reach it in the process, and those that only held the routes went with them. With step 9's first pull request the simulator keeps no book of its playbacks: `Playbacks`, `Simulator.playbacks` and `Simulator.cursors`, `playback.start`, `playback`, `state`, `command`, `set_pace`, `set_targets`, `stop_playbacks` and `stop_epoch`, and `policy_port.policy_port` are gone, and with them what read the book: a stop that reached an epoch through its playback (a stop is the scheduler's, `scheduler.cancel`), an authorisation told to the playbacks (a change of the simulator's reaches every epoch it keeps through the store), a deletion refused while a replaced playback still wrote an epoch, and a running epoch said `paused` because a playback held its clock. The consumer's reads by a run's identifier (`services.consumer`'s `Reads`, `runs`, `run`, `greenhouse`, `observations`, `events`, `outcomes`) went too; its cursors and batches stay, for the policy's port and a stored epoch's records. A `Playback` is made by whoever plays a run: a worker, an experiment's runner, the port's server and examples 01 and 02, which read its records by a cursor (`records_after`). What only the book used of `Playback` went with it: its successor once replaced, its `rearranged` run, a fork's manifest for it, and what the book asked of it (`plays`, `epoch_held`, `epoch_kept`, `has_epoch`, `stop_if_working`, `stopped`, `standing`, `failed`, `working`). Its second pull request took away the `paused` field of a position and of a stored run, which nothing set any more, from their published schemas and the viewer's contracts, and with it the viewer's words for a run a playback held: the replay's note that a playback holds the run's clock, and *Paused* for a running run in the replay's header, the lists of runs and a deletion refused. A follow-up took `PlaybackCommand.RESTART` away, with which a `Playback` started its run over as a new epoch: a new epoch of a run is a worker's resume or a fork, and the policy's port, on one playback's epoch, no longer follows its run into another. Not delivered, as the decision says: a consumer interface and a gateway over a worker's epoch, live ([future work](../future-work.md#runs-and-playbacks-after-p17)) |
| P22.4 | **A new run's form:** the dialog leads with starting a run and lists the runs under it; *Open in the viewer* goes. The form: what the scenario is, its duration, its weather, the crops to read, with a way to make a new scenario from this one (`src/builder/CopyScenario.tsx`), and how fast to compute it; the seed small and optional, as it is now. The start route takes the duration and the weather | A run is started with a duration and a weather of the form's, and repeated by its seed | Done ([decision 0075](../../decisions/0075-a-runs-weather-and-a-shorter-duration-are-its-own-as-its-seed-is.md), proposed): the start route takes `weather`, one of the scenario's by name, and `duration_days`, from 1 to the scenario's own, each its own when not given. A weather other than its own makes another run, as a seed does; fewer days are the same run ended sooner, its first days' digests the whole run's. The epoch keeps both, so that its worker, a resume and a fork run as it was started, and the runs listed and a position say its `weather`, under which the replay draws its scene. The runs dialog's form (`RunsDialog.tsx`) asks for them: its days, from 1 to the scenario's own, which it refuses otherwise before asking, and its weather, in words (`weatherName`), each its scenario's own until changed and asked for as none then; the scenario's crop in words, with *Make a new scenario from this one*, which opens the builder with the scenario chosen to copy (`/builder#copy=<id>`, `CopyScenario`); the pace; and the seed, small and optional, as before. Its fields are the design system's `Field`, its button `Button`, its link `LinkButton` and its problems `Notice`, the controls keeping the start page's look until P19.8. *Open in the viewer* is gone. `/view` stays: the builder's *Open in the viewer*, QA mode and links from before still reach it. Its own climate play, which decision 0074 kept and left to this step, went after P22.8: no link but the builder's led to it, and a run computed and kept is watched in a replay. `/view` draws the moment chosen on its sliders and day steps, and nothing moves it on by itself.8, which reshapes the viewer's panels. The dialog leads with the form, open from the start under the scenario's name, and lists its runs under it (*Its runs*); the *New run* button that opened the form is gone, and the builder's `/#run=<id>` opens the same dialog as `/#runs=<id>`. Not delivered: a run longer than its scenario, and the weather's QA overrides (decision 0075's open questions) |
| P22.5 | **The pace, said once:** a replay's "s a day" is how fast it shows; the form's is how fast the run computes, and each says so | Neither reads as the other | Done: the replay's choice reads *Shows a day in*, each of its paces in seconds (`10 s`), so it says how fast the replay shows the run (`src/replay/ReplayTransport.tsx`). The form for a new run asks for *Seconds to compute a day*, and its hint says that this is the run's own clock, a day taking no less, while its replay shows the days at a speed of its own (`src/landing/RunsDialog.tsx`). The climate run's *Pace* in the scenario's own view, a step of five minutes, an hour or a day, is another thing and stays as it is: a replay shows none of the climate run's controls |
| P22.6 | **The scene keeps up** (D3): measured first, server cost per moment against the viewer's loads; then the replay skips moments or loads ahead (`useReplayMoment.ts`, `src/fields/useClimateLoads.ts`) | At 10 s a day, the panels and the timeline show the same day | Done ([measured](#the-scenes-lag-measured-p226)): the panels trailed the timeline by one moment's latency, 0.5 days on average, and read the same day as it 54 to 59% of the time, since a moment costs its climate field's grid run, 1 to 5 s, however far it skips. While a replay plays over the climate field, it now asks for the field ahead, one moment at a time, with the field drawn kept on show (`momentAhead`, `src/scene/useReplayMoment.ts`): the moment the position will stand at when the answer arrives, at the pace and the last field's time, on the whole hour, and, before a day ends, the next day's first minute, in time for the timeline to find it there. Each is drawn once the simulator has answered and the position has reached it, with its glazing and openings, which wait on the same grid run and are then answered at once. At 10 s a day the panels read the same day as the timeline 96 to 97% of the time, 0.2 days behind on average. A position that goes back, or stops playing, draws its own moment as before. Not delivered: the first 0.25 to 0.9 s of each day, while the moment drawn is asked for again rather than taken from the answer ahead, the two read different days; the panels hold the day's last moment, around noon by day, until midnight; a browser spec, as the pace a machine keeps decides the figures, which are measured instead |
| P22.7 | **The start page:** a title that says what the place is for, the two choices equal, one under the other with "or", each with an icon, fewer words and a tooltip on each button. Before P19.8, which moves the landing page's controls, or folded into it | The walk's words, read on the page | Done, folded into P19.8 as its last pull request: the start page's title says what the place is for, *Simulate a greenhouse's climate and crop*, with no line under it, centred. *Open a scenario* and *Build a scenario* are cards of one look and width, at most 720 px, centred under it, one under the other with *or* between them, each heading with an icon of `src/icons/`, `SearchIcon` and `PencilIcon`, new and drawn as the others are; the builder's two buttons stand on one line. Four lines went: the one under the title, the search's (its placeholder now), the builder's and the upload's note. Each button says what it does on hover, in a few words in `title`, as the replay's do, the design system having no tooltip: *Contribute*, *Open the builder*, the upload, and a run's *Replay*, *Stop*, *Resume* and *Delete*, which the runs dialog shares. Its words, in `Landing.tsx`, `UploadScenario.tsx`, `RunParts.tsx`, `RunControls.tsx` and `RunDelete.tsx`, are held by their tests; the start page's and the runs dialog's baselines were drawn again. The styles weigh 34.95 kB, 0.18 kB more. Not delivered: a tooltip on a disabled *Stopping*, which the browser would not show, its chip saying it instead; the search keeps its label, *Scenario*, which `Field` requires |
| P22.8 | **The viewer's panels,** three changes one after another: the header names a run or a simulation, with the version and not the commit except on a branch; a *Display* card beside *House*; equipment in groups, without identifiers. With P19.11 | Each read on the page | Done, in three pull requests after P19.11's. **The name (#699):** the info panel's heading, *greenhouse-sim viewer* whatever it showed, names it: *Simulation of* a scenario, by its name, *Plant lab*, or *Test scene*; a replay's header reads *Run of* its scenario. The line at the panel's foot says `simulator 0.7.0`, and only on a branch of its own the branch and the commit, `simulator 0.7.0 · feat/a-panel at abc1234`; on `main`, at a tag or outside a checkout, the version alone. The commit stays on its hover and in QA mode's manifest. **A *Display* card (#700):** the display options, a fold at the panel's top, are a card beside *House*, before *Equipment*, and at the top where there is no *House*: *Colours* and *Overlays*, each folded to its line (`Colours: their own`, `Overlays: hiding wind`), and *QA mode*, a switch of its own. **Equipment in groups (#701):** the equipment's and the openings' rows are listed by kind (the scene's `device_kind` and `opening_kind`), a kind of more than one named over its rows, *Fans*, *Roof vents*, and each row by what tells it apart, *right*, *1*; a kind of one keeps its name. A switch and a slider keep the piece's whole name. Their lines say a kind at once when its pieces stand alike, `Equipment: fans 100%; heater, dehumidifier off`. Held by `InfoPanel.test.tsx`, `ReplayHeader.test.tsx`, `DisplayOptions.test.tsx`, `EquipmentControls.test.tsx` and `OpeningControls.test.tsx`, and in the browser by `info-panel.spec.ts`, `overlays.spec.ts` and the specs that read a heading or a line; the replay's, the viewer's and the run panels' baselines were drawn again. The styles weigh 34.12 kB, the scripts 1,723.24 kB. `/view`'s own climate play went after these three (see P22.4). Not delivered: a name for a group's rows other than what follows the kind in the scene's label, so that a piece the scene names otherwise keeps its whole name in its group |
| P22.9 | **The panel under the view:** it folds as the side panels do, their arrows taking the panel's whole height or width; each button says what it does on hover, *Fork* first; *Delete* in place of *Other runs*. With P19.10 | Each read on the page | Done, after P19.10's two pull requests: **It folds:** a stripe the page's whole width along the transport's upper edge, `PanelStripe`'s, its arrow ▼ open and ▲ folded, folds the transport away and the scene takes the room; folded, it stays at the page's foot to open it again. It is kept for the next visit under the side panels' key, `greenhouse-sim.folded`, as `transport`, each page writing only its own (`panelFolds.ts`). The side panels' stripes take the height of the panel beside them, the info panel's and the HUD's, measured as it grows or folds (`PanelSide`), and never less than the 96 px tab they were. The side's whole height was tried: its stripe then stood over the view's edge below the panel, and took a click meant for the scene (`e2e/selection.spec.ts`). **On hover:** each button says what it does in `title`, as the start page's do: *Fork from here*, "Make a new run from this moment; asks first"; *Delete*, the start page's "Delete this run and what it kept; asks first"; *The run it came from*; *Home*, "Go to the start page", on every page that has it; *Previous day*, *Play*, *Pause*, *Next day*, and *Follow the newest day*, pressed or not; and the stripe. **Delete:** the start page's `RunDelete` stands where *Other runs* did: asked again, then the run is deleted through `deleteRun`, and the page goes to the start page. A run being computed is stopped first, then deleted, on every list of runs and in the replay: its question says so before it is answered ("This run is being computed: deleting it stops it first, then deletes it and what it kept."), its button reads *Stop and delete*, and *Delete* says on hover "Stop this run, then delete it and what it kept; asks first". A worker of the simulator asked has stopped by the time it answers; one it cannot signal stops at its next look at the store, and until then the run reads *stopping* and says so in `notDeleted`'s words: "This run is stopping: it can be deleted once it reads Interrupted." Held by `ReplayHeader.test.tsx`, `ReplayTransport.test.tsx`, `PanelStripe.test.tsx`, and by `e2e/replay.spec.ts` and `e2e/panels.spec.ts` in the browser; *Other runs*' users in the browser specs go to the scenario's runs by its address. Moved: the replay's and the viewer's page baselines, both themes. The styles weigh 34.19 kB; the scripts 1,721.47 kB. Not delivered: a tooltip on a disabled button, which the browser does not show |
| P22.10 | **The QA scenario** below, run and recorded | Each step passes in the browser | Done: run and recorded [at `e23ccf6e`](#recorded-at-e23ccf6e), twice; five steps passed, and the sixth found a defect. A run of 10 days under a cold spring day, its seed left empty, opened in its replay following it. One *Play* at 10 s a day watched it to its end. The panels read the timeline's day 98% of the time, at most 0.64 days behind; they read different days only around midnight, for at most 1.0 s, which is P22.6's known stretch, not "throughout". A heating target raised while it computed made one `POST …/changes` and no fork, and took from the worker's moment. The panel under the view folded and opened again, and each of its buttons says what it does on hover. *Delete* took the run, finished by then, and landed on the start page; a second run deleted while it computed was stopped first. Started again at seed 42, the scenario's own, it was the same run: the same run id, and records equal to those of a run with no seed. The defect: the run started again took the deleted epoch's number, which a deleted epoch keeps (#710 fixes it). Not walked: a level of equipment steered, a change refused, a slower machine |

P22.1 comes first: P22.2 and P22.3 take away the steering the viewer's play has,
and P22.4's *Open in the viewer* goes with P22.3. P22.5 to P22.9 are independent
of them and of each other, but for P22.7 to P22.9 lining up with P19's steps.

## P22.3's pull requests

As [decision 0074](../../decisions/0074-the-viewers-play-and-the-playbacks-http-surfaces-go.md)
planned them, each under about 500 lines but for generated files and files
deleted whole, in this order, so that no browser spec loses what it watches
before the code it watched goes. All are done; step 9 took two pull requests,
the simulator's side and then the viewer's words:

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
   of [future work](../future-work.md) P17 and P18 left to P22.3 are settled
   there, this step is done and the decision accepted.

*Open in the viewer*, in `src/landing/RunsDialog.tsx`, is P22.4's.

## The scene's lag, measured (P22.6)

**Method.** One machine (Intel i9-14900K, 32 threads, 31 GB), Python 3.14, commit
`2c926594`, the viewer's production build behind `vite preview`, in headless Chromium
(Playwright 1.64). A run of the reference greenhouse at seed 7, computed by a worker as
fast as it goes while it was replayed, and other work on the machine (load 7 to 9), so
**the times are upper bounds**. The replay played for 60 s at 10 s a day, once from
Day 1 and once from Day 12: every request the page made recorded with its
`Server-Timing`, and every 250 ms the day the timeline (`replay-moment`) and the panels
(`climate-time`) read. Then the climate field asked with the replay's own query, one
request at a time, and several at once, for each moment's own cost.

**The lag is one moment's latency, not a queue.** In both minutes the panels were 0.5
days behind the timeline on average and 0.9 at most, and read the same day as it 60% of
the time; the lag did not grow through the minute. The timeline moved 5.9 days and the
panels showed 18 moments, 3 a day: the replay already skips, moving to the position's
newest moment each time a field arrives (`src/scene/useReplayMoment.ts`), so nothing
waits behind it. A field took 2.6 to 2.9 s (median; 1.1 to 5.5) and the next was asked
0.2 s after it (at most 0.5), at the position's next answer, asked every second. A field
was on its way 93% of the time: a cycle of 3.3 s, a third of a day at this pace, and the
panels show the moment the position stood at one to two cycles before.

**A moment costs its climate field, however far it skips.** The field at a moment is a
grid run started from the whole house's air an hour before the moment's hour began
(`window_start`, `greenhouse_sim/climate/day.py`), so a moment in another hour than the
last costs one to two hours of the air cell by cell; the whole house's air on the way
costs little. The field, one request at a time:

| Moment asked | At night | By day (fans and vents on) |
| --- | --- | --- |
| On the hour (a grid run of 1 h) | 0.9 to 1.0 s | 2.6 to 2.9 s |
| At 59 minutes past (a grid run of 2 h) | 1.9 to 2.0 s | 5.2 to 5.3 s |
| A day on from the last, at midnight | 0.9 to 1.0 s | |
| In the same hour as the last | 19 ms a minute on, 0.5 s half an hour on | |

A moment 2.4 h on, as a second of play at 10 s a day moves, costs 1.0 to 4.6 s through
a day, 25 s for the day's ten. The replay's field is worked out by the simulator from
the run's plan, not read from the epoch the worker stores. Once it is there, the rest of
a moment is cheap one request at a time: the glazing, the openings and the equipment
3 ms each, the house's air 16 to 120 ms, the scene 90 ms (2.6 MB), the crop 100 to
150 ms (3 to 4 MB). In the replay they are asked with the field, and the glazing and the
openings wait for its grid run (2.5 s each, as long as the field).

**Requests per day shown.** 223 requests in the minute: 37 per simulated day, 12 per
moment shown. Each moment asks for the field, the glazing, the openings, the house's air
twice (the run's own, and the same run all off), the equipment, the weather and the
scene; each day the crop and the day's weather; and the position is asked every second.
At most 10 or 11 were on their way at once, 6 or more 17 to 22% of the time, for a few
hundred milliseconds as a moment's requests start together; the browser's six
connections hold the field back little (its time in the browser is within 0.4 s of the
simulator's).

**Moments at once.** The simulator answers each request in a thread of one process.
Three fields of different hours by day, asked at once, took 4.8 s together, against
7.7 s one after another; two at night 1.4 s, against 2.0 s: 1.4 to 1.6 times as many
moments, no more. At 10 s a day the simulator draws 3 to 5 moments a simulated day,
whichever are asked.

**The fix chosen: load ahead, one moment at a time.** Skipping more cannot close the
gap: the replay skips already, a moment costs the same however far it skips, and the lag
stays one cycle (0.3 to 0.6 days at 10 s a day here; up to a day and a half where a moment
takes the walk's 4 to 6 s, as D3 saw). Loading several moments ahead at once cannot either,
since the simulator works them only 1.5 times as fast. Rounding to the hour alone, a skip,
would halve a moment's cost by day and the lag with it, without making the day the same.
What closes it is to ask, while the field on show stays up, for the moment the position
will stand at when the answer arrives, on the whole hour, whose grid run is the shorter,
and to draw it when the timeline reaches it; and, before a day ends, for the next day's
first minute, so that the panels change day as the timeline does.

**Before and after.** The same recording, once the run was computed: 90 s of play at
10 s a day from Day 1 and from Day 12, each on a simulator started afresh, which keeps
no climate run of the one before. Before is commit `e0cd94c6`, after this step's.

| | Before, Day 1 | After, Day 1 | Before, Day 12 | After, Day 12 |
| --- | --- | --- | --- | --- |
| The panels and the timeline on the same day | 59% | 97% | 54% | 96% |
| The panels behind the timeline, on average and at most | 0.47, 0.90 days | 0.22, 0.63 days | 0.51, 0.90 days | 0.25, 0.63 days |
| The longest the two read different days | 5.9 s | 0.6 s | 5.9 s | 0.9 s |
| Moments shown, of 8.9 days | 28 | 32 | 27 | 30 |
| Fields asked, and the simulator's time on them | 29, 80 s | 64, 64 s | 27, 78 s | 62, 64 s |
| Requests, and at most at once | 339, 10 | 404, 9 | 335, 10 | 391, 9 |

Every stretch on different days after is the first 0.25 to 0.9 s of a day: the next
day's first minute is drawn as the timeline reaches it, and the field drawn is asked
again then, which the simulator keeps and answers in 0.1 to 0.5 s. A moment is asked
twice, ahead and drawn, so the fields asked double; the moments on the whole hour cost
less, and the simulator spends less time on them for more moments shown. The day's
last moment is one that leaves the time to ask for the next day's first minute once it
is drawn, which by day, at 2.5 to 3 s a moment, is around noon: the panels hold it until
midnight.

Not measured: the browser's own time to parse and draw a moment, the development
server, and a slower machine, where D3's two days were seen.

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

### Recorded at `e23ccf6e`

Run on 11 November 2026 on `e23ccf6e`, `main`, on the machine of P22.6's measure: an Intel Core
i9-14900K, 32 threads, 31 GB, Linux, Python 3.14.4. The API ran from the workspace's Python,
`python -m greenhouse_sim.api --port 8741`, with `--drafts` and `XDG_STATE_HOME` in a folder of
its own, so that its run store held this walk's runs alone. The viewer was its production build
(`npm run build`), served by `vite preview` on port 8742 with `SIMULATOR_API_PORT=8741`. A
Playwright 1.65 script drove headless Chromium 158 at 1280 by 720. It took a screenshot at each
step, and read what is recorded here from the page, its requests and the run store. The scenario
was walked twice, each time on an API started afresh with an empty store. The first walk used
Chromium's default, which here draws in software (SwiftShader). The second, which the table
gives, drew on the machine's integrated graphics (ANGLE on Vulkan, Intel RPL-S), asked for with
`--enable-gpu --use-angle=vulkan`. The machine was shared with other work: its load average,
read every 5 s, was 1.2 to 5.2 during the first walk and 3.5 to 5.2 during the second.

**How step 2 was measured.** From the press of *Play*, every 250 ms, a timer in the page read
what the timeline says (`replay-moment`), what the panels say (`climate-time`), the run's
status, the heating targets' line, and the position and the frontier on the timeline's slider.
Both say a moment as "Day 10, 02:24". The gap is the timeline's moment less the panels', in
days; "the same day" compares their day numbers. The samples came 250 ms apart, 356 ms at most.

| Step | Result | What was seen |
| --- | --- | --- |
| 1. Start a run of 10 days, another weather, no seed | Passed | The start page's search found *Reference greenhouse*, and its dialog opened on the form. *Days* was set to 10 of its 120, and *Weather* to "cold spring day", one of five: "its own" and four days. *Seconds to compute a day* kept its 10, and *Seed* was left empty ("The scenario's own"). *Start run* asked `POST /api/scenarios/reference_greenhouse/runs?seconds_per_day=10&weather=cold_spring_day&duration_days=10`. The answer was run `reference_greenhouse-climate-b01d2f93`, epoch 0, with no seed. The page went to its replay, following the newest day (`&follow=1`): *Run of Reference greenhouse*, "the scenario's seed · epoch 0 · everything kept", *Queued*, then *Running* within a second. |
| 2. Watch it compute with one *Play* at 10 s a day | Passed, but for a second around each midnight | *Shows a day in* read 10 s, and *Follow the newest day* was pressed. *Play* was pressed once: it let go of *Follow the newest day* and played on to the end. The run took 110 s of its worker's time and 72 s of CPU. The replay waited at the frontier, which moves on a day at each commit: the position stood 0.64 days behind it on average, 1.5 at most. In 130 s and 522 samples, the panels read the timeline's day 97.9% of the time. They were 0.19 days behind it on average and 0.64 at most. They read different days in five stretches, each at a midnight, of 1.0 s twice and 0.25 s three times. In each, the timeline said "Day 5, 00:00" or "Day 8, 02:23" while the panels still held the day before at 10:00 or 11:00. This is what P22.6 left: the panels hold the day's last moment, about 11:00 here, until the next day's first is drawn. At the end the timeline read "Day 10, 24:00" with the panels at "Day 10, 11:00", and the panels reached "Day 10, 24:00" 3 s later. The first walk, drawn in software, gave 94.0%, 0.19 and 0.64 days, and eight stretches, the longest 1.34 s. |
| 3. Raise the heating target by day while it computes | Passed | 25 s into the play, the timeline read "Day 1, 09:36", with one day computed. The panels said "This run is being computed: a target or a level set here is given to it, from the moment its worker has reached, not the one shown, and nothing forks." *Heating targets* read 18 °C by day and 16 °C by night. The day's target was set to 24 with *Set from the run's next minute*. The panels said "Asked of the run: waiting for its worker to take it.", then, 1.1 s later, "The run took the latest change from Day 2, 17:20.": the worker's next minute, not the moment shown. The requests were one `POST …/epochs/0/changes` and two `GET …/changes`. Of the walk's 817 requests, none was made of `…/forks`; the address stayed the same, and no fork was asked about. The epoch's log held one entry, `targets_changed`, `heating_day` 24 from 148,800 s (Day 2, 17:20). The targets' line read "24 °C by day" once the replay reached Day 2, 24:00. The run's first day's records equal those of the same run unchanged (step 6); its days 2 to 10 differ. The first walk took it from Day 2, 18:58, 0.1 s after it was asked. |
| 4. Fold the panel under the view, open it, hover its buttons | Passed | At the run's end. The stripe's ▼, *Fold the controls under the view*, folded it: the transport was gone, and the scene grew from 454 to 626 px tall. The stripe stayed at the page's foot, 1280 px wide and 14 px tall, its button now *Open the controls under the view*, which opened it again at 454 px. Each button's `title`, read with the pointer over it: the stripe "Fold the controls under the view", or "Open the controls under the view" while folded; *Previous day* "Go back a day"; *Play* "Play from this moment", disabled at the end; *Next day* "Go on a day". While the run computed, *Pause* said "Pause at this moment", and *Follow the newest day*, not pressed, "Go to the newest day computed, and stay at it as the run computes"; it is not shown once the run has ended. *Shows a day in* is a select with a label and no `title`. In the header, *Home* says "Go to the start page", *Fork from here* "Make a new run from this moment; asks first", and *Delete* "Delete this run and what it kept; asks first". A headless screenshot does not show the browser's tooltip itself: these are the page's words. |
| 5. Delete the run from the replay, land on the start page | Passed, the run having finished | The run had finished 21 s before. *Delete* asked *Delete this run* or *Keep it*, with no note. Confirmed, it made one `POST …/epochs/0/delete`, and the page went to the start page, whose list no longer held the run. A run being computed was deleted after step 6, the same way: a third run of the same id, with no seed, *Running* 35 s in. Its *Delete* said "Stop this run, then delete it and what it kept; asks first". Its question said "This run is being computed: deleting it stops it first, then deletes it and what it kept.", with *Stop and delete this run* and *Keep it*. Confirmed, the page made `POST …/delete`, answered 409, then `POST …/stop` and `POST …/delete`, and went to the start page; the list no longer held the run. The browser's console reports the 409 as a resource that failed to load. |
| 6. Start the same run again at the seed the first one used | Passed for the run, failed for its number | The first run used the scenario's own seed, 42 (`random_seed` in its manifest). The page never says 42: the form says "The scenario's own", the replay "the scenario's seed". The form was filled as in step 1, with *Seed* 42. The answer was the same run id, `reference_greenhouse-climate-b01d2f93`, "seed 42 · epoch 0", computed in 108 s. A run is told apart by its run id, made from its scenario, layout, weather and seed. What it kept is told apart by its commits' trajectory digests. Each digest covers the objects committed by their names, which hold the epoch's number, so digests compare only between epochs of the same number. The first commit's digest, day 1, equalled the first run's, `8e2537f9b662…`. The nine after it differ, since the first run was steered from Day 2 and its log is in its digests. The second run's ten digests were the same in both walks, each in a store of its own, ending `9e05e56cfeb6…`. A fourth run, asked of the API with no seed and as fast as it computes, kept records equal byte for byte to the second's: its 30 segment files of 10 days. **Defect:** the run started again was epoch 0, the deleted run's number. Deleting an epoch leaves a mark so that its number is not used again (`delete_epoch`, and the route's own words). A fork and a playback number after it, but starting a run counted only the epochs the store holds (`workers.queued`). So the new run took the deleted number, its worker cleared the mark, and the deleted run's address opened the new run. The fourth run took the deleted third's number, 1, too. Fixed in #710, with a regression test; this walk ran on the code before it. |

Not walked, and held by tests that pass on this commit: a level of equipment, a door or a vent
asked of a running epoch, and a change refused or never taken (`replay/changes.test.tsx`,
`EpochSteering.test.tsx`), which no browser spec walks, as P22.1 says; a change in a finished
run's replay making a fork (`replay.spec.ts`, "a level set in the replay of a finished run forks
it"); the fold kept for the next visit and opened from the keyboard (`replay.spec.ts`, P22.9's
test); a run whose worker another process holds, which reads *stopping* until it is interrupted
(`Landing.test.tsx`); and the dark theme.

Not measured: the browser's tooltip as drawn, which a headless browser does not show; a slower
machine, where D3 saw two days of lag.

Seen beside the steps: with the run ended at Day 10, *Schedule* still read "Next at Day 11,
08:00: fan left 100% and 1 more.", a command after the end of a run cut to fewer days than its
scenario's 120. It is left for a change of its own.

## Open questions

- **Duration and weather as a start's inputs:** settled by [decision 0075](../../decisions/0075-a-runs-weather-and-a-shorter-duration-are-its-own-as-its-seed-is.md),
  accepted as P22 closed: a weather and fewer days are a run's, as its seed is, and a
  longer season a scenario of its own.
