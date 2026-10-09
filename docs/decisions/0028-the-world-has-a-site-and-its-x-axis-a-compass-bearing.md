# 0028: The world has a site, and its x axis a compass bearing

**Status:** Accepted
**Date:** 2026-10-09

## Context

Decision 0007 fixed the world's axes, and 0016 the greenhouse's frame within
them, but nothing said where the world lies on the Earth. P07 brings the
weather, whose wind comes from a compass direction and whose day follows the
local clock. P08 brings the sun, which needs a latitude, a longitude, a time
zone and the way the house faces. Every scenario so far has its greenhouse
at the world's origin, along its axes, and its runs start at midnight UTC.

The options were a bearing for the greenhouse alone, or for the world. A
site may hold several greenhouses (0016), each turned its own way, while the
wind and the sun are the same for all of them.

## Decision

- **A site places the world on the Earth** (`greenhouse_sim.world.site`):
  latitude and longitude in degrees north and east, elevation in metres
  above sea level, an IANA time zone, and the compass bearing of the world's
  x axis. Every scenario has one, by default near Bleiswijk in the
  Netherlands, where the recorded greenhouse data the adapters read were
  taken.
- **Bearings are degrees clockwise from north,** as a compass reads them,
  from 0 up to 360. The world's y axis points 90° anticlockwise of its x
  axis, seen from above, as its right-handed, z-up axes have it.
- **By default x points east,** so y points north and z up: the east, north,
  up convention of robotics (ROS REP 103) and of local geographic frames.
- **A greenhouse's own bearing** is the world's, turned by its envelope's
  origin (0016). Nothing else in the simulator states a direction on the
  Earth.
- **The wind's direction is the one it blows from,** as meteorology gives
  it, in the same bearings. Its velocity in the world's axes points the
  other way.
- **A scenario's runs start at its start date's midnight at its site,** in
  its time zone. The instant is published in UTC, as the protocol's records
  are.

## Consequences

- The weather (P07) and the sun (P08) need no other way to know where the
  world lies, or which way the house faces.
- Turning a greenhouse to face south is a change to its site's bearing, or
  to its envelope's origin; its layout, written in its own frame, is
  untouched.
- Runs started at midnight UTC before this decision now start an hour or
  two earlier, at the site's midnight. Their air is the same; only the
  instants their observations are stamped with move.
- A site far from sea level has a lower standard pressure, which the air's
  density will follow once the openings' flows depend on it (P07.6).
