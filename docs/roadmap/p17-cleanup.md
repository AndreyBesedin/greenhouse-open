# P17 clean-up

**Status:** open. Part of [P17](p17-runs-and-playbacks.md).

A walk of the viewer's pages at commit `28701e05`, on the Vite development server
with a machine's GPU (ANGLE Metal, Apple M2), found these defects. The ones fixed
at once have their own pull requests. These are left, each small enough to be done
on its own, and are ticked off here as they are.

They were seen in that walk, and have not been looked at since. A pull request that
takes one checks first that it is still there.

## To do

### Medium

- [x] **The builder has no way home.** Its only ways out are "Save and go back",
  which saves, and a link that appears after a run. The viewer has a Home button.
- [x] **A scene opened without following a run is not framed on the house.** The
  camera stays at its default (5.2, -5.2, 5.2) and the house runs off under the View
  panel. It came before the landing page: the presets have looked at the world's
  origin since the viewer's first camera, and only a followed run was framed.
- [x] **A house with no equipment has no climate run.** It has no climate field and
  gets fixed light, not the sun. It now has one, as any other house has: its crop
  already lived in that run's house air, so the field's grid run is what is added,
  about 6 to 12 s on tomato_compartment for the first moment drawn in an hour of the
  run. Its sensors and its run's id stay its own airflow's, so that no run or record
  changes. The sensor lab, the one packaged house with sensors and no equipment, reads
  its prescribed gradient on purpose, about 8 °C from the climate drawn beside it.
- [x] **Low: a built house with sensors and no equipment.** Its climate run and its sensors
  read two different airs, as the sensor lab's do, but nothing in such a house says the
  gradient was meant. A scenario that is not packaged now reads its climate run, under a
  climate run's name, and the packaged houses' runs and records stay as they are.

### Low to medium

- [x] **A replay reads one moment three ways:** "Day 10, 02:24", "day 9, 2 h 24 min",
  and a tick "day 0" under "Day 1, 00:00".
- [x] **Deleting a running run shows a raw id** and says to stop the run, and the
  dialog has no stop control. It says which run, by its seed and epoch, and what to
  do, and a worker's run has a *Stop* button beside it.

### Low

**Landing page and runs dialog**

- [x] A paused playback stays "Running".
- [x] Progress means two different things on the same page. At `bf8758ae` a row's bar and
  its words both say the days computed, on the start page and in the dialog.
- [x] A saved draft is not on the start page. The card to build a scenario lists the latest three,
  each opening in the builder, and no list when none is saved.
- [x] `GET /playback` shows a red 404 in the console on a first run. None in the third
  walk: not on `/view` of any of the seven scenarios, nor on a first run from the dialog.
- [x] Close drops the keyboard focus. Fix in #528. A dialog opened by the address has
  nothing to give focus back to, by Close or Escape.
- [x] `/#runs=x` stays in the address, and `/#run=no_such` shows nothing.
- [x] Run rows are not aligned: in a dialog *Replay* and *Follow* sit above *Stop* and
  *Delete*, and the bars differ in width from row to row. The links no longer keep the
  browser's colour.

**Builder**

- [x] "Run this revision" with an empty seed gives no feedback beside the button.
- [ ] Some text is too pale in the dark theme.
- [x] `builder/portable.py` words its refusals as "format None" and "not JSON:
  Expecting value…".

**Viewer**

- [x] The green test cube shows behind an error.
- [x] "before day one is not available" is awkward wording.
- [x] The wind label shows through the light panel, and faintly through the dark one.
- [x] The console reports the deprecation of `THREE.Clock`, from `@react-three/fiber`.
  Still there at `a2c27d2a`, with three 0.187.0. Left for upstream: the viewer makes no
  `Clock`, and `@react-three/fiber` 9.8.2, its latest release, makes one for every canvas.
  Its next major, 10.0.0, drops it
  ([pmndrs/react-three-fiber#3741](https://github.com/pmndrs/react-three-fiber/issues/3741)),
  and so does its alpha.6; the warning goes with the move to 10.0.0 once it is released.
- [x] The console reports a 404 for `favicon.ico`.

**Replay**

- [x] Play at the end does nothing.
- [x] `aria-valuenow` can be fractional.
- [x] The legend says "not computed yet" on a finished run.
- [x] At phone width the panel covers the scene. The last tick is labelled now. At
  390 by 844 a replay's scene is 472 px high with its lower 212 px under the panel (a
  fork's, whose header is taller, 383 and 172); the stripes that fold the panels are not
  drawn at this width, so it cannot be moved aside. Turned to 844 by 390, the panel covers
  the scene almost whole.
  The panel scrolls and nothing else overflows.
  Closed as out of scope: the viewer is not made for phones ([the roadmap](README.md#not-goals-for-the-first-versions)).

### From a second walk

A walk of the merged pages at commit `2db9f3b7`, on the same setup, with forks and the
panels in a replay.

- [x] **Medium: forks cannot be told apart on the start page or in the runs dialog.**
  They read as rows of "Seed 143 · epoch N". A fork's row now says what it came from,
  as its replay's header does.
- [x] **Low to medium: a fork's controls stay enabled at a run's end.** "Fork from here
  with these levels" and the targets form can still be used, and the refusal gives the
  end in seconds ("the run ends at 1209600 s"). Fix in #520.
- [x] Each page load of a followed house with no climate sends one burst of 404s before
  the list of fields answers.
- [x] A mid-day fork opens at its day's start, while its subtitle names the fork's moment.
- [x] A fork of a deleted parent keeps a "The run it came from" link that ends in a
  "cannot be replayed" notice.
- [x] With equipment set in a replay, the slider stands at full while its label says
  "off", until the fork is made.
- [x] Keys pressed faster than the answers move from the old position: Home then PageUp
  landed from the old place.

That walk did not repeat the phone width, and did not see the fork panels in the light
theme. The third did.

### From the third walk

The record of P17.10, at commit `bf8758ae`, on the Vite development server with a machine's
GPU (ANGLE Metal, Apple M2): see [its record](p17-runs-and-playbacks.md#recorded-at-bf8758ae).
What is still open above was still there where it looked; it did not measure the builder's
pale text.

**Medium**

- [x] **A far seek leaves the house's air working for minutes.** The air at a moment is worked
  out from the run's start, for the run and for the same run all off, and a checkpoint does not
  shorten it. On an idle server, a finished 120-day `tomgro_house` from the start to Day 87:
  the moment moved in 0.3 s, the scene in 1.1 s, the air answered in 96.6 s. On
  `reference_greenhouse`, at Day 120, the climate had not answered 40 s after the seek. A request
  is worked to its end though the page has moved on: a drag sent 10 seeks, each its own work,
  beside the others, and while they ran a seek went unanswered for over 3 s and the
  panels read "mixing" for over 40 s. The line's words are fixed in #519. #533 stops the work of a
  request whose client has gone, and #534 draws the run's own air first, in under 2 s from Day 87,
  from the checkpoint of its day. The same run all off still costs about 100 s of a core the first
  time on each server, and only its dashed line waits for it; P18 keeps that as a debt.
- [x] **A run whose server was killed cannot be stopped.** A server ended by `kill` leaves its
  workers computing, by design (P17.9, a lease). The next server lists the run as Running, and
  its *Stop* says "No worker of this simulator has this run. One the viewer plays stops with
  its playback, and one whose worker is gone soon reads Interrupted", which does not happen
  while the worker lives; *Delete* says to stop it first. Nothing in the viewer ends it: the run
  goes on to its end, or its process is killed. Ctrl-C ends the workers as it should. A stop
  now reaches such a worker through a request in the store, as a change does.
- [x] **A replay left open across a restart stood still in silence.** It read "Running" and
  asked for its position once a second, 40 404s in 40 s. Fix in #516.

**Low**

- [x] *Resume* forgets a run's pace: a run asked for at 20 s a day, stopped and resumed,
  finished its 10 days in under a minute. The route takes a pace and the row sends none.
- [x] A run's date is its date in UTC: at 00:25 on 4 November, an hour ahead of UTC, the rows
  say "Nov 3".
  A test holds UTC, so it may have been meant.
- [x] A disabled *Play* or *Fork from here* looks as it does enabled. Fix in #521.
- [x] A replay's schedule counts days from 0 under a timeline that counts from 1: at Day 40,
  01:01, "Next at day 39, 8 h 00 min". Fix in #523. By the code, a sensor's reading and a camera's
  frame are said the same way in a replay; not walked.
- [x] A fork's timeline has no label where it begins. Fix in #524.
- [x] The runs dialog keeps "still being computed: stop it, then delete it" up after Stop,
  beside a row reading Interrupted. Fix in #525.
- [x] The note under the levels set names their identifiers ("Set roof_vent_1"). Fix in #527.
- [x] The address of a run with files missing still opens its replay, which says Finished. The
  lists offer no link to it, so this takes an address kept from before. It now says the run
  cannot be replayed and why, also for a finished run that lost its last commits, which left no
  gap to see.
- [x] A fork in another layout is another run's epoch, and can read "epoch 0 · forked from
  epoch 0" with no word of the layout.
- [x] At phone width the builder's page is 463 px wide in a window of 390: the pane that draws
  the house lies to the right of the form.
- [x] A panel's fork takes the moment it shows, by design, so under load *Fork from here with
  these levels* at a transport reading Day 2, 24:00 forked from Day 1, 24:00, the field still
  on its way. The subtitle then says so.
- [x] A playback that failed, until it is started again, answers every reader with a 500 and no
  words. `GET /consumer/v1/runs` then lists no run at all, of any scenario, since it asks each
  playback kept for its state. By the code, the viewer's panel says "the simulator answered 500"
  and has no start button, though a start now plays the run again. It now answers 409 with its
  epoch's `reason`, the list leaves it out, and the panel says why and offers to play it again.

### From P13's acceptance: an epoch resumed after its authorisation changed

Found on 2026-11-06 while writing a test for [P13](archive/p13-actions.md#acceptance-criteria)'s
criterion 8, on the one-plant box with an epoch store, and not seen in a walk.

- [ ] **Medium: an epoch whose authorisation changed while it ran cannot be carried on.**
  The local operator's heater level, due at noon, was refused at noon, "no longer
  authorised", after the right to set levels was withdrawn at 6 h; its first day was kept,
  its checkpoint without the action. Carried on from that checkpoint (`workers.resume`, then
  `Playback.resume_at`), the epoch stops with a conflict, "the log of epoch 0 of …, applied
  again, does not give the outcomes it kept". A change of authorisation is not in the
  epoch's log (`LogEntry`) or anywhere in the run store, so the log is applied again under one
  authorisation, the resuming simulator's: under the first, the level is executed; under the
  one that withdrew it, it is refused at once, "not authorised to set_level". Each differs
  from the outcome kept, so the epoch refuses to go on rather than carrying a withdrawn action
  out. The same epoch with no withdrawal is carried on to its end. The likely remedy is to log
  each change of authorisation with its moment, and apply it again at that moment as a plan
  given is; a test that resumes such an epoch is to come with the fix.

## Not covered by the walk

About 75 of the first walk's 101 screenshots were not opened. The second walk did not
try a replay after a simulator's restart, or a server-side refusal of a file too large to
upload; the third tried both, and both behaved (its record says how).

The third walk took about 110 screenshots and opened about 45, those of each kind of page. The
whole browser suite was not run locally: 84 tests of the first stage, then the specs of the
replay, the workers and the scenario file. It did not walk a scenario
with no equipment under a climate run, which came after the commit walked, a recorded weather
ticked out and uploaded, the *Fork this run with these moves* at a run's end, or more than one
browser at once.
