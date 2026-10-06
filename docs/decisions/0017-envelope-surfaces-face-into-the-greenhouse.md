# 0017: Envelope surfaces face into the greenhouse, and carry a category

**Status:** Accepted
**Date:** 2026-10-05

## Context

P01.2 generates the greenhouse's first surfaces from its envelope (decision
0016): the floor and four walls. The roof, doors and vents follow in P01,
and airflow (P04), radiation (P08) and sensors (P06) will all read these
surfaces. They need to agree on which side of a surface is which, and on
what each surface is, without looking at how a viewer draws it.

## Decision

- An envelope surface is a rectangle (`Plane`) placed in the greenhouse's
  frame, with an identifier and a category (`floor`, `wall`; the roof,
  glazing, doors and vents join as P01 adds them).
- A surface's front, its plane's +z, faces into the greenhouse. A test
  checks this for every surface, so none is inverted.
- Surfaces are named as seen from the greenhouse's origin, looking along its
  length: the right side wall stands along y = 0, the left along y = width,
  the front end wall at x = 0 and the back at x = length.
- The surfaces close the greenhouse: every edge they share is shared by
  exactly two of them. A test checks this, with the open top expected until
  the roof arrives.
- The scene shows each surface as an entity of its category's kind (`FLOOR`,
  `WALL`), in place of the provisional ground.

## Consequences

- A consumer that wants outward normals, as CFD boundaries usually do, turns
  each surface's front around in one place.
- New surfaces only add categories and names; the facing and closing tests
  cover them as they come.
- The greenhouse's bounds now lie on its walls. The viewer draws them only
  with the dimensions, as an outline that takes no clicks.
