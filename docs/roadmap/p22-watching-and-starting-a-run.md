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
| P22.3 | **The viewer's own play goes,** with a decision on the playback routes and the policy's port | No control starts a playback in the viewer; the browser tests that used it watch in the replay | Proposed |
| P22.4 | **A new run's form:** the dialog leads with starting a run and lists the runs under it; *Open in the viewer* goes. The form: what the scenario is, its duration, its weather, the crops to read, with a way to make a new scenario from this one (`src/builder/CopyScenario.tsx`), and how fast to compute it; the seed small and optional, as it is now. The start route takes the duration and the weather | A run is started with a duration and a weather of the form's, and repeated by its seed | Proposed |
| P22.5 | **The pace, said once:** a replay's "s a day" is how fast it shows; the form's is how fast the run computes, and each says so | Neither reads as the other | Proposed |
| P22.6 | **The scene keeps up** (D3): measured first, server cost per moment against the viewer's loads; then the replay skips moments or loads ahead (`useReplayMoment.ts`, `src/fields/useClimateLoads.ts`) | At 10 s a day, the panels and the timeline show the same day | In progress: measured ([below](#the-scenes-lag-measured-p226)). The panels trail the timeline by one moment's latency, 0.5 days on average and 0.9 at most here, not by a queue: the replay skips already, and a moment costs its climate field's grid run, 1 to 5 s, however far it skips. The fix proposed is to load ahead: ask for the moment the timeline will reach when the answer arrives, and for each day's midnight before it ends, one at a time, and draw each when the timeline gets there |
| P22.7 | **The start page:** a title that says what the place is for, the two choices equal, one under the other with "or", each with an icon, fewer words and a tooltip on each button. Before P19.8, which moves the landing page's controls, or folded into it | The walk's words, read on the page | Proposed |
| P22.8 | **The viewer's panels,** three changes one after another: the header names a run or a simulation, with the version and not the commit except on a branch; a *Display* card beside *House*; equipment in groups, without identifiers. With P19.11 | Each read on the page | Proposed |
| P22.9 | **The panel under the view:** it folds as the side panels do, their arrows taking the panel's whole height or width; each button says what it does on hover, *Fork* first; *Delete* in place of *Other runs*. With P19.10 | Each read on the page | Proposed |
| P22.10 | **The QA scenario** below, run and recorded | Each step passes in the browser | Proposed |

P22.1 comes first: P22.2 and P22.3 take away the steering the viewer's play has,
and P22.4's *Open in the viewer* goes with P22.3. P22.5 to P22.9 are independent
of them and of each other, but for P22.7 to P22.9 lining up with P19's steps.

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

**The fix proposed: load ahead, one moment at a time.** Skipping more cannot close the
gap: the replay skips already, a moment costs the same however far it skips, and the lag
stays one cycle (0.3 to 0.6 days at 10 s a day here; up to a day and a half where a moment
takes the walk's 4 to 6 s, as D3 saw). Loading several moments ahead at once cannot either,
since the simulator works them only 1.5 times as fast. What closes it is to ask, while
the field on show stays up, for the moment the position will stand at when the answer
arrives (its moment, with the pace times the last field's time added, on the whole
hour, whose grid run is the shorter) and to draw it when the timeline reaches it; and,
before a day ends, for the next day's midnight (about 1 s, a night hour), so that the
panels change day as the timeline does. One field on its way at a time, as now: the
simulator does no more work than it does now, and a moment drawn is late by the
estimate's error rather than by the whole latency. Rounding to the hour alone, a skip,
would halve a moment's cost by day and the lag with it, without making the day the
same. Not measured: the browser's own time to parse and draw a moment, the development
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

## Open questions

- **The playback routes and the policy's port.** The viewer's own play uses the
  playback routes, and P15's port reads live playbacks. Whether they stay for
  consumers, or a run's epochs take their place, is P22.3's decision.
- **Duration and weather as a start's inputs:** whether they make another scenario
  or stay a run's, as its seed is.
