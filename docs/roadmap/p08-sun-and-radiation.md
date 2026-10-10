# P08: Sun position, glazing and radiation propagation

**Status:** in progress: P08.1 and P08.2 done, P08.3 next. Part of the
[simulator roadmap](README.md).

## Goal

Make sunlight physically meaningful: the sun moves over the site through a
run, the glass passes less of it at grazing angles, the greenhouse's frames
and fixtures cast shadows, and anything inside, a sensor, a plant or the
air, can ask how much light and radiant heat reaches it where it stands.

## Dependencies

P01 (the envelope, its frames and its glazing's surfaces) and P02 (the
fixtures that obstruct light). P07 gives the site, the run's clock and the
outside's radiation and cloud cover. P03's plants can consume the light;
P06's PAR sensor, unavailable until now, can read it.

## Direction

- **Physical radiation has units, and is not the viewer's lighting.** The
  viewer may light its scene from the sun's direction, but the radiation
  plants, sensors and the air take is computed by the simulator, in W/m²
  and µmol/m²/s, from explicit models.
- **Deterministic and offline:** the sun's position comes from a published
  algorithm, the outside's radiation from the weather source, and nothing
  needs a network.
- **One radiation model, any consumer:** a point and the orientation of the
  surface there give the irradiance; a field, a sensor, a plant and the
  climate run's solar gain all ask it the same way.
- **Each part testable on its own,** with a known answer: the sun's path
  against reference values, the glass's transmission bounded and falling
  with the angle, a shaded point getting no direct beam.

## Design

Nothing in the simulator knows the sun yet. The weather state carries
global radiation and cloud cover, both unused; constant weather's radiation
is nothing, and a synthetic day's is nothing too. PAR sensors stand, but
report nothing. Plants take a daily light integral from the plant lab's
presets. The climate run passes no sunlight through the glass.

### 1. The sun's position

- **The algorithm:** NOAA's solar equations (after Meeus): the Julian day
  of the moment, the sun's mean anomaly and equation of centre, its
  apparent longitude and declination, the equation of time and the hour
  angle at the site's longitude. Elevation includes the atmosphere's
  refraction, NOAA's approximation. Accurate to about 0.01° between 1800
  and 2100, which is far finer than any shadow needs.
- **Its result:** the sun's elevation and its azimuth, clockwise from
  north as every bearing is (decision 0028), at any moment of a run, and
  its direction in the world's axes through the site's compass.
- **Tests:** NREL's Solar Position Algorithm's published example (17
  October 2003, Golden, Colorado) within 0.05°; at either equinox, the
  noon elevation is 90° less the latitude, within the declination's
  drift; at the solstices, the declination is ±23.44°; the sun is due
  south at solar noon at a northern site.

### 2. The outside's radiation

The weather's `global_radiation_w_m2` is the global horizontal irradiance
(GHI), the sun's and the sky's together on a level surface.

- **A synthetic day** gains one: a clear sky's, by Haurwitz's model
  (GHI = 1098 cos Z e^(−0.057 / cos Z) W/m², Z the sun's zenith angle),
  dimmed by the day's cloud cover after Kasten and Czeplak
  (1 − 0.75 (N/8)^3.4, N in oktas). Nothing while the sun is down.
- **Constant weather** keeps the radiation it is given, but only while the
  sun is up. **Recorded weather** gives its own.
- **Direct and diffuse:** GHI is split by the Erbs correlation on the
  clearness index, the share of the radiation above the atmosphere that
  reaches the ground: the diffuse horizontal part (DHI) from the sky, and
  the beam, as direct normal irradiance (DNI) along the sun's direction.
- **PAR:** photosynthetically active radiation is taken as 47% of the
  global shortwave's energy, at 4.57 µmol per joule: about 2.15 µmol/m²/s
  for each W/m² of GHI.

### 3. The glass

- **Transmission:** each glazed surface passes a share τ of the beam that
  reaches it, its normal-incidence transmittance (0.85 for single glass)
  times an incidence-angle modifier, 1 − b₀ (1 / cos θ − 1), b₀ = 0.1
  (ASHRAE), never below nothing: the glass passes less as the sun grazes
  it. The diffuse sky's transmittance is the modifier's mean over the
  hemisphere.
- **Which surface:** the beam reaching a point inside crosses the envelope
  where the ray from the point towards the sun leaves it: a roof slope or
  a wall, and its own angle there.
- **Tests:** transmission lies between 0 and 1 and falls with the angle;
  the radiation inside is less than outside.

### 4. Shadows

- **What casts them:** the greenhouse's frames (posts and rafters), its
  gutters, the fixtures that obstruct light (P02's obstruction `light`:
  crop gutters, benches, slabs, rails, pipes, obstacles), and the plants'
  crowns (section 6). Equipment obstructs no light, as its description
  says.
- **How:** a point is in the beam's shadow if the ray from it towards the
  sun meets any of them before leaving the house: exact ray tests against
  boxes and cylinders, vectorised over many points at once.
- **The diffuse sky** is shaded by the structure as a whole: by the share
  of the roof the frames and gutters cover, from the envelope's geometry.
- **Tests:** a point under a solid fixture gets no direct beam; a point in
  the open gets all of it.

### 5. The radiation inside

- **At a point, on a surface:** the beam, transmitted and unshaded, on a
  surface facing a given way (its cosine with the sun), and the diffuse
  sky, transmitted and shaded, by the surface's view of the sky,
  (1 + n_z) / 2. Ground-reflected light is left out.
- **As a field:** a `radiation` field on the climate run's grid
  (decision 0026), at a moment of a run: PAR on a level surface at each
  cell's centre, in µmol/m²/s, and the shortwave irradiance in W/m².
  Each moment's is worked out when asked, and kept.
- **PAR sensors** read it where they stand, as P06's other sensors read
  the air.

### 6. Plants

- **Each plant's crown** is a cylinder about its stem, as tall as its
  visible stem and about 0.25 m across, which shades the light below and
  beside it.
- **Each plant's PAR:** the mean over its crown's top of the PAR reaching
  it, with the other plants' crowns, the fixtures and the frames in the
  way; and its daily light integral, mol/m²/d, summed through the day.
- **The plant model consumes it:** a `SunlitEnvironment` gives each plant
  its own daily light integral, in place of a preset's, through the plant
  model's `Environment` contract (decision 0024), with the rest of its
  day's climate from the scenario. Joining the crop's days to the climate
  run's seconds is P09's.

### 7. Solar heat

The sun is most of what warms a greenhouse by day, and P05 and P07 left it
to here.

- **The radiation reaching the floor** inside, transmitted and shaded,
  heats the air in the lowest layer of cells above it: a share η = 0.7 of
  it, the rest taken by the ground and the crop's water, which P08 does
  not model.
- **The whole house** takes the same total.
- **This moves P07's numbers by day** under synthetic weather, which now
  has sunshine; constant weather without radiation, and every night, are
  unchanged. The numbers that move are recorded again.

### 8. Viewer

- **The sun in the scene:** a marker in the sky in the sun's direction,
  an arrow from it to the house, and the day's sun path as an arc, all
  following the climate run's time slider; the Weather panel adds the
  sun's elevation and azimuth.
- **Sunlight and shadows:** in a scenario's view with a climate run, the
  scene's light comes from the sun's direction, and casts shadows; at
  night, only the ambient light. The QA pages keep their fixed light, so
  their screenshots do not move.
- **The radiation field** as a false-colour slice, as the climate's are,
  with its legend.
- **Each plant's PAR** in the inspector, its moment's and its day's.
- **Clouds:** a QA override of the weather's cloud cover (`&clouds=80`),
  so that the sky can be dimmed without another weather.

### 9. Scenarios

- **A solar lab** (`solar_lab`), the final QA's, on 20 March 2026, the
  spring equinox: the climate box's house and frames, a row of plants of
  different heights along it, a bench that shades part of the floor and
  PAR sensors either side of it, under a clear spring day.
- **Every other scenario** keeps its date, so its sun is January's.

## Steps

| Step | Commit summary | Status |
| --- | --- | --- |
| P08.1 | `feat(solar): implement deterministic sun position model` | Done |
| P08.2 | `feat(viewer): add sun lighting and visible shadows` | Done |
| P08.3 | `feat(radiation): define the radiation field and its units` | Planned |
| P08.4 | `feat(glazing): add transmission and incidence-angle attenuation` | Planned |
| P08.5 | `feat(radiation): add geometric shadow and occlusion tracing` | Planned |
| P08.6 | `feat(radiation): add plant canopy interception hooks` | Planned |
| P08.7 | `feat(radiation): add the diffuse sky and the clouds' attenuation` | Planned |
| P08.8 | `feat(climate): warm the house with the sun` | Planned |
| P08.9 | `test(radiation): add equinox day-path visual regression` | Planned |

### P08.1: The sun's position

NOAA's solar equations, the sun's elevation and azimuth at a moment of a
run and its direction in the world's axes, served with the weather, and the
viewer's sun marker and arrow. Visible result: the sun's marker and arrow
move across the sky as the time slider scrubs. Tests: the reference values
of section 1.

#### As implemented

- **`solar.position`:** NOAA's equations, `sun_position(moment, site)` giving
  the elevation (refraction included), the azimuth, the declination and the
  equation of time; `SunPosition.direction(site)` the unit vector towards
  the sun in the world's axes.
- **Against references:** NREL's SPA example to 0.003° in zenith angle and
  0.002° in azimuth; at the default site (52° N) the equinox's noon sun
  stands 38.0° high, June's 61.4° and December's 14.6°; the declination
  turns at ±23.44°; the equation of time is 14 minutes slow in mid-February
  and 16 fast in early November; the sun rises in the east, stands south
  at solar noon (11:50 UTC at the March equinox, at 4.5° east) and sets in
  the west.
- **Served with the weather:** `GET /api/scenarios/{id}/weather` gains `sun`
  and `sun_direction`. The scenarios' runs start on 1 January, so their
  noon sun stands about 15° high in the south.
- **The viewer:** the Weather panel, opened, gives the sun's elevation and
  bearing, or that it is below the horizon; the scene draws the sun as a
  marker in the sky, at 1.5 times the house's longer side from its middle,
  with an arrow along its light to the house and a label, while it is up.

### P08.2: Sunlight and shadows in the viewer

The scene's light from the sun's direction, with shadow maps, and the
sun-path arc. Visible result: the frames and fixtures cast shadows that
swing through an accelerated day. Tests: the light's direction is the
sun's, and it points the other way in the evening from the morning; the
QA pages' light is unchanged.

#### As implemented

- **The day's sun:** `GET /api/scenarios/{id}/weather/day` gains `sun` and
  `sun_directions`, one for each of its moments, as the weather at a moment
  has them.
- **The light (`scene/SunLight`):** in a scenario's view with a climate
  run, while the sun is up, the fixed light gives way to a directional
  light from the sun's direction, at twice the house's longer side from
  its middle and shining at it, its shadow camera covering the house and
  4 m around it. Everything opaque in the scene casts a shadow and
  everything takes them; glass and the other see-through faces cast none.
  At night only the ambient light is left. The sun's light is stronger
  than the fixed one (2 against 1.2), and the sky's ambient light dimmer
  beside it (0.35 against 0.6), so that what lies in shade reads as such:
  a 15° winter sun lights a level floor only faintly. The canvas draws
  shadows only then, so every other view, the QA pages among them, is lit
  and drawn as before. The canvas says which light it has (`data-light`:
  `fixed`, `sun` or `night`) for the browser tests.
- **The viewer's shadows are the renderer's:** drawn from every opaque
  part, equipment's bodies among them, while the radiation (P08.5) counts
  only what obstructs light.
- **The sun's path:** the day's positions while the sun is up, joined at
  the sun marker's reach, in the same views as its light.
- **The sun's arrow** is now a 2 m pointer from its marker towards the
  house: drawn the whole way, its head, a quarter of its length, filled a
  view taken near it, and the light and shadows now show the way.

### P08.3: The radiation field and its units

The outside's radiation as GHI, a synthetic day's from the clear-sky model,
its beam as DNI, PAR from it, and the radiation at a point or surface
inside, the beam alone and unshaded for now; the `radiation` field.
Visible result: a false-colour floor of PAR. Tests: a level surface takes
DNI cos Z; a surface facing the sun takes DNI; the units' conversions.

### P08.4: The glass

Transmission through each surface by its incidence angle, and the surface
the beam crosses. Visible result: the radiation inside is visibly less
than outside, and changes with the sun's angle. Tests: transmission is
bounded and falls with the angle; energy decreases through the glass.

### P08.5: Shadows

Ray tests against frames, gutters and light-obstructing fixtures. Visible result: the floor's false colour shows the frames' and
fixtures' shadows. Tests: an occluded point gets no beam, a clear one all
of it.

### P08.6: Plants

Plants' crowns, each plant's PAR and daily light integral, the
`SunlitEnvironment`, and the inspector's PAR. PAR sensors read the field.
Visible result: two plants, one shaded and one exposed, compared in the
inspector. Tests: a shaded plant's PAR is less; a plant grown in its own
light grows less where it is shaded.

### P08.7: The diffuse sky and the clouds

The Erbs split into beam and diffuse, the diffuse sky's transmission and
structural shading, and the clouds' dimming, with the QA override.
Visible result: the cloud slider softens the shadows and dims the whole
floor. Tests: under full cloud nearly all is diffuse; the total falls with
cloud.

### P08.8: Solar heat

The floor's absorbed radiation as heat in the air above it, on the grid
and in the whole house; P07's numbers that move recorded again. Visible
result: on a clear day the shut house warms well above the outside by
noon. Tests: the heat gained is η times the radiation absorbed; at night
nothing changes.

### P08.9: Equinox day-path visual regression

Morning, noon and evening golden views of the solar lab, and radiation
probes with numeric reference values. Visible result: the three views'
screenshots. Tests: the screenshots, and the probes' values.

## Final QA: `solar-day`

Accelerate through the solar lab's clear equinox day and check that:

- the sun's path moves correctly;
- the visual shadows move;
- the glass reduces the incoming radiation;
- fixtures and plants make local shade;
- the radiation heat-map follows the day;
- the inspector shows a plant's local PAR;
- the cloud control changes the balance of direct and diffuse light.

## Acceptance criteria

- [ ] Physical radiation has units and is separate from the scene's
  lighting.
- [ ] Radiation can be queried locally.
- [ ] The greenhouse's geometry affects the light it transmits.
- [ ] The plant model can consume local PAR or radiation.

## Known approximations

- **No ground-reflected light,** and no light reflected inside the house:
  only the sun's beam and the sky's diffuse light reach a point.
- **The diffuse sky is isotropic,** and shaded by the structure as a whole,
  not traced ray by ray.
- **A plant's crown is a cylinder,** not its leaves; the plant lab's
  organ-level leaves do not cast shadows on each other yet.
- **The glass is clean and dry:** no condensation or dirt on it.
- **Solar heat goes to the air at the floor** by a fixed share; the ground
  and the crop's transpiration, which take the rest, are not modelled.

## Decisions taken without review

The design was written and built without a review first, at the user's
request; these are the choices it makes, each with what it set aside, for
a later review.

1. **The sun's algorithm:** NOAA's equations, rather than NREL's full SPA,
   which is ten times longer for accuracy no shadow can show.
2. **Solar heat is in P08** (section 7), though the plan's P08 does not
   list it, as P05 and P07 left the sun's heat to it; the alternative was
   to defer it to P09.
3. **The radiation field** lives on the climate run's grid, so that
   sensors, plants and the solar heat share one sampling, rather than on a
   separate floor map.
4. **The clear sky and the clouds** come from Haurwitz's and Kasten and
   Czeplak's simple models, and the split from Erbs's, rather than a
   turbidity-based clear-sky model: they need no atmospheric data.
5. **Plants consume their light** through the existing `Environment`
   contract, as a daily light integral, rather than hourly; P09 joins the
   clocks.
6. **The QA scenario** is a new `solar_lab`, dated at the equinox, rather
   than moving any scenario's date, which every recorded number depends
   on.
