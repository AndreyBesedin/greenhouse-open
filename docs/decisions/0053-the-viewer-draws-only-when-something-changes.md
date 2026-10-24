# 0053: The viewer draws only when something changes

**Status:** Accepted
**Date:** 2026-10-24

## Context

The viewer's main view drew every frame, so that the HUD could measure its
frame rate. Only the QA pages drew on demand, so that a heavy scene drawn in
software left their screenshots alone.

CI draws in software, as decision 0015 says: Playwright's headless browser
uses SwiftShader, on runners with no graphics card. The tomato compartment
with its CFD field takes about 200 ms of the page's main thread a frame
there, and drawn frame after frame, the page answers input only between
them. The browser test of that field (`e2e/fields.spec.ts`, "the
compartment's air as OpenFOAM solved it is drawn as any field is") failed
seven times between 21 and 24 October, three of them on `main`. In one
failure its trace shows the clicks it makes taking 7.7, 10.6 and 8.1
seconds, past its 30-second timeout.

Measured locally on the same test (Chromium's headless shell, in software,
on an Apple M2 with 8 cores), drawn every frame against only on change:

| | Every frame | On change |
| --- | --- | --- |
| A task's wait for the main thread, the view still (median) | 206 ms | 5 ms |
| Unfolding the air field's section | 1,678 ms | 126 ms |
| Choosing streamlines | 2,226 ms | 486 ms |
| Choosing a slice | 2,915 ms | 301 ms |
| The test, in three runs | 11.3 to 12.3 s | 2.7 to 3.3 s |

The page's wait is 5 ms because that is the shortest a timer waits once the
page has used several in a row, not because a frame is drawn. A still view
has nothing new to draw; drawing it again costs every test, and every
laptop, its share of a processor.

## Decision

- **The main view and a camera's picture draw only when something
  changes** (react-three-fiber's `frameloop="demand"`). A change React
  makes to an object's props draws a frame by itself, as does an object
  added or removed.
- **A change made other than through props asks for a frame**
  (`invalidate()`): a mesh's instances written in an effect, the
  renderer's clipping planes, a light's shadow camera, a camera set from a
  sensor's intrinsics. A camera the controls move has its world matrix
  brought up to date as it moves, since a click is picked from that matrix
  and can come before the frame that would update it.
- **The HUD measures frames drawn in a row.** A gap of more than a second
  between two frames is the view standing still, not a slow frame. Still,
  the HUD's frame rate reads "idle", and its frame time stays that of the
  last frames drawn in a row.
- **The benchmarks are unchanged.** They measure while the camera orbits
  (decision 0015), when the view draws frame after frame as before.

## Consequences

- A component that changes what is drawn other than through its props, and
  does not ask for a frame, shows a stale view until something else draws
  one. The browser tests, which click on what is drawn, and the visual
  checks, which compare what is drawn, are where that is seen; a new such
  component asks for its frame where it makes the change.
- A still page leaves the main thread free, so a click is answered in
  milliseconds, not seconds, on CI's software renderer, and a still view
  costs no processor.
- The HUD's frame rate is a rate while the view draws. An idle scene's
  cost is read from its frame time, or by orbiting it.
- Something that moves on its own, with no change from React, such as an
  animation, would have to ask for a frame on every frame it runs. Should
  the viewer come to have many, drawing every frame while they run is the
  decision to revisit.
