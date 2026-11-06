# P22: Watching and starting a run

**Status:** proposed, not started. What the [QA of 2026-11-04](qa-2026-11-04.md)
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
- The playback routes and the policy's port ([P15](archive/p15-policy-port.md)), until a
  decision of this project says what becomes of them.
- The design system's rules ([P19](p19-design-system.md)): new controls are its
  components, and a change of look is one of its named visual changes.

## Steps

| Step | Work | Accepted when | Status |
| --- | --- | --- | --- |
| P22.1 | **Steer a running epoch from the replay:** a target or a command changed in a replay's panels, while its epoch runs, posts to the epoch's changes and reads them back, in place of a fork | A change made in a replay steers the running epoch, from its moment, and a finished epoch still forks | Proposed |
| P22.2 | **One *Play*:** *Follow* goes; the replay follows a run that is computing | Every list of runs offers one way to watch each | Proposed |
| P22.3 | **The viewer's own play goes,** with a decision on the playback routes and the policy's port | No control starts a playback in the viewer; the browser tests that used it watch in the replay | Proposed |
| P22.4 | **A new run's form:** the dialog leads with starting a run and lists the runs under it; *Open in the viewer* goes. The form: what the scenario is, its duration, its weather, the crops to read, with a way to make a new scenario from this one (`src/builder/CopyScenario.tsx`), and how fast to compute it; the seed small and optional, as it is now. The start route takes the duration and the weather | A run is started with a duration and a weather of the form's, and repeated by its seed | Proposed |
| P22.5 | **The pace, said once:** a replay's "s a day" is how fast it shows; the form's is how fast the run computes, and each says so | Neither reads as the other | Proposed |
| P22.6 | **The scene keeps up** (D3): measured first, server cost per moment against the viewer's loads; then the replay skips moments or loads ahead (`useReplayMoment.ts`, `src/fields/useClimateLoads.ts`) | At 10 s a day, the panels and the timeline show the same day | Proposed |
| P22.7 | **The start page:** a title that says what the place is for, the two choices equal, one under the other with "or", each with an icon, fewer words and a tooltip on each button. Before P19.8, which moves the landing page's controls, or folded into it | The walk's words, read on the page | Proposed |
| P22.8 | **The viewer's panels,** three changes one after another: the header names a run or a simulation, with the version and not the commit except on a branch; a *Display* card beside *House*; equipment in groups, without identifiers. With P19.11 | Each read on the page | Proposed |
| P22.9 | **The panel under the view:** it folds as the side panels do, their arrows taking the panel's whole height or width; each button says what it does on hover, *Fork* first; *Delete* in place of *Other runs*. With P19.10 | Each read on the page | Proposed |
| P22.10 | **The QA scenario** below, run and recorded | Each step passes in the browser | Proposed |

P22.1 comes first: P22.2 and P22.3 take away the steering the viewer's play has,
and P22.4's *Open in the viewer* goes with P22.3. P22.5 to P22.9 are independent
of them and of each other, but for P22.7 to P22.9 lining up with P19's steps.

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
