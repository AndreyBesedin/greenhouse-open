# 0018: Openings lie on a surface, and expose an aperture

**Status:** Accepted
**Date:** 2026-10-06

## Context

P01.5 adds doors and vents to the greenhouse's envelope. Airflow (P04) will
treat them as the boundary's openings, and climate control (P05) will open
and close vents. Both need to know where an opening is, how far it is open
and how much area it opens, from the same description the geometry comes
from (decisions 0016 and 0017).

Cutting each opening out of its host surface would keep the drawn geometry
exact, but it splits surfaces into pieces and edges into partial edges, and
the closed-envelope invariant (every edge shared by exactly two surfaces)
would no longer be simple to state or test.

## Decision

- An opening is a rectangle on one host surface, given in the host's own
  x-y plane (its centre, width and height), with a kind (door, roof vent,
  side vent) and an open fraction from 0 (closed) to 1. The envelope refuses
  an opening that does not fit on its host, or shares another's name.
- Vents are top-hung: hinged along their upper edge, they swing outward, up
  to their largest angle (45 degrees by default). Doors slide sideways along
  their wall, just outside it.
- An opening's aperture is the area it opens in the boundary. A door opens
  its open fraction of its area. A vent opens its "curtain", the gap at its
  free edge plus a triangle at each side,
  `W * 2L * sin(angle / 2) + L^2 * sin(angle)` for a vent `W` wide along its
  hinge and `L` deep, but never more than its frame, `W * L`.
- The host surface is not cut. An opening lies on it, and the scene draws
  its panel where it stands open, with its open fraction and aperture.
- The simulator's API sets openings for a scenario's scene (`?open=`),
  checking the envelope afresh; the viewer's sliders ask it, so the
  geometry stays generated in Python.

## Consequences

- P04 reads each opening's place, normal and aperture from the envelope, and
  treats it as the boundary's open area there.
- The drawn host glass still covers an open vent's hole. Cutting it can come
  later, behind the same description, if it starts to matter.
- A vent of another kind, such as a side-hung or pivoting one, is a new kind
  with its own swing and aperture.
