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
- [ ] **A scene opened without following a run is not framed on the house.** The
  camera stays at its default (5.2, -5.2, 5.2) and the house runs off under the View
  panel. Whether this came before the landing page is not known.
- [ ] **A house with no equipment has no climate run.** It has no climate field and
  gets fixed light, not the sun. Whether it should have a climate run, and at what
  cost, is open.

### Low to medium

- [x] **A replay reads one moment three ways:** "Day 10, 02:24", "day 9, 2 h 24 min",
  and a tick "day 0" under "Day 1, 00:00".
- [ ] **Deleting a running run shows a raw id** and says to stop the run, and the
  dialog has no stop control.

### Low

**Landing page and runs dialog**

- [ ] A paused playback stays "Running".
- [ ] Progress means two different things on the same page.
- [ ] A saved draft is not on the start page.
- [ ] `GET /playback` shows a red 404 in the console on a first run.
- [ ] Close drops the keyboard focus.
- [ ] `/#runs=x` stays in the address, and `/#run=no_such` shows nothing.
- [ ] Run rows are not aligned, and their links keep the browser's default colour.

**Builder**

- [x] "Run this revision" with an empty seed gives no feedback beside the button.
- [ ] Some text is too pale in the dark theme.
- [x] `builder/portable.py` words its refusals as "format None" and "not JSON:
  Expecting value…".

**Viewer**

- [ ] The green test cube shows behind an error.
- [x] "before day one is not available" is awkward wording.
- [ ] The wind label shows through the light panel.
- [ ] The console reports the deprecation of `THREE.Clock`, from `@react-three/fiber`.
- [x] The console reports a 404 for `favicon.ico`.

**Replay**

- [ ] Play at the end does nothing.
- [ ] `aria-valuenow` can be fractional.
- [ ] The legend says "not computed yet" on a finished run.
- [ ] At phone width the panel covers the scene, and the last tick is missing.

## Not covered by the walk

About 75 of its 101 screenshots were not opened. The whole browser suite was not run
locally, a replay after a simulator's restart was not tried, and neither was a
server-side refusal of a file too large to upload.
