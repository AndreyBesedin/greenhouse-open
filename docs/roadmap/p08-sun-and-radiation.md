# P08: Sun position, glazing and radiation propagation

**Status:** in progress: P08.1 to P08.7 done, P08.8 next. Part of the
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
  PAR sensors either side of it, under a clear spring day. (As built in
  P08.6: its plants are of one height, and a stack of crates shades them
  and the floor.)
- **Every other scenario** keeps its date, so its sun is January's.

## Steps

| Step | Commit summary | Status |
| --- | --- | --- |
| P08.1 | `feat(solar): implement deterministic sun position model` | Done |
| P08.2 | `feat(viewer): add sun lighting and visible shadows` | Done |
| P08.3 | `feat(radiation): define the radiation field and its units` | Done |
| P08.4 | `feat(glazing): add transmission and incidence-angle attenuation` | Done |
| P08.5 | `feat(radiation): add geometric shadow and occlusion tracing` | Done |
| P08.6 | `feat(radiation): add plant canopy interception hooks` | Done |
| P08.7 | `feat(radiation): add the diffuse sky and the clouds' attenuation` | Done |
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

#### As implemented

- **`solar.sky`:** Haurwitz's clear sky; the sun's irradiance above the
  atmosphere, 1361 W/m² by 1 ± 0.033 through the year, greatest on
  3 January; `OutsideLight`, the GHI split into the beam's DNI and the
  diffuse DHI. Until P08.7 the light is all beam, as far as the beam can
  carry it: never more than the sun gives above the atmosphere, the rest
  diffuse, so that DNI cos Z + DHI is always the GHI. PAR is
  0.47 × 4.57 = 2.148 µmol/m²/s per W/m².
- **The weather's radiation:** a synthetic day's is now a clear sky's
  under the sun where it stands, nothing while it is down; the clouds
  dim it from P08.7. Constant weather's radiation is only while the sun
  is up. Nothing used the radiation yet, so no number of a climate run
  moves; the sun's heat comes in P08.8.
- **`solar.inside.Sunlight`:** the light at a point inside on a surface
  facing a given way, `on(normal, time_s, point)`: the beam by its cosine
  with the sun, the diffuse by the surface's view of the sky; and `at`,
  on a level surface at each of the climate grid's cells' centres. For
  now every point takes the light as it is outside.
- **The radiation field rides on the climate field:** rather than a field
  of its own, the climate run's field at a moment carries two more
  channels, `par` (µmol/m²/s) and `irradiance` (W/m²), so that one
  request gives the air and its light at the same moment, under the
  sunlight the view is drawn in, and a probe reads both.
  `AirQuantity` gains them. The field schema's version is unchanged:
  its quantities grew, but its shape did not.
- **Served with the weather:** `GET /api/scenarios/{id}/weather` gains
  `light`: GHI, DNI, DHI and PAR.
- **The viewer:** a slice can be of `par` or `irradiance`
  (`&fieldView=slice&slice=par:z:0.25`), its legend "PAR (µmol/m²/s)"; a
  probe reads both, after the air; the Weather panel adds the light
  ("229 W/m², PAR 493 µmol/m²/s", or "dark"); the day's chart adds the
  sunshine. Under a clear spring day at 12:45 on 1 January the climate
  box's floor takes 229.5 W/m², 492.9 µmol/m²/s of PAR.

### P08.4: The glass

Transmission through each surface by its incidence angle, and the surface
the beam crosses. Visible result: the radiation inside is visibly less
than outside, and changes with the sun's angle. Tests: transmission is
bounded and falls with the angle; energy decreases through the glass.

#### As implemented

- **`solar.glass`:** `transmittance(cos θ)`, 0.85 × max(0, 1 − 0.1 (1/cos θ − 1)),
  nothing beyond about 85°; the diffuse sky's, its mean over the
  hemisphere in closed form, 0.773.
- **Which surface (`Glazing`):** the envelope's walls and roof slopes, each
  its own flat polygon facing in, as `world.envelope` generates them, so
  any envelope it describes, multi-span among them, is traced the same
  way. For each point, the ray towards the sun leaves through the nearest
  surface it meets inside that surface's outline (within a micrometre of
  its edges, so that a ray along a seam leaves too), at that surface's
  angle; vectorised over all the grid's cells at once.
- **`Sunlight`** now takes the envelope; the beam on a surface is the
  DNI by its cosine with the sun times what the glass passes on its way
  there, the diffuse sky's DHI by the surface's sky view times 0.773.
  `on(point, normal, time_s)` now needs the point.
- **What it does:** at 12:45 on 1 January under a clear sky, the climate
  box's floor takes 194.4 W/m² (417.5 µmol/m²/s of PAR) where the outside
  takes 229.5: the beam crosses the south wall 15° from square. At the
  equinox's noon, cells whose beam crosses the south roof slope, 38° from
  square, take 331 W/m² of 400, and those whose beam crosses the north
  slope, 66° from it, 290.
- **Left as they are:** a beam leaving one span's roof and crossing
  another's is passed once only; an open vent's or door's aperture passes
  the beam as its glass would.

### P08.5: Shadows

Ray tests against frames, gutters and light-obstructing fixtures. Visible result: the floor's false colour shows the frames' and
fixtures' shadows. Tests: an occluded point gets no beam, a clear one all
of it.

#### As implemented

- **`solar.shadows.Shadows`:** the solids that shade the beam, each a box
  or a finite cylinder placed in the world: the structure's gutters and
  members, and the layout's fixtures that obstruct light
  (`Layout.obstructing(Obstruction.LIGHT)`, which leaves the equipment
  out). `lit(points, towards)` tests the ray from every point towards the
  sun against every solid exactly, in each one's own frame: a box by its
  three slabs, a cylinder by its side and its two ends; vectorised over
  the points and over batches of 64 solids. A point inside a solid is in
  its shadow; one on its top face is not.
- **The structure's solids are the envelope's:** `Gutter.solid()` and
  `Member.solid()` (`world.envelope`) now give the channel and the round
  bar the scene draws, at the sizes the scene had for them, so that what
  is drawn and what shades are the same; the scene's files did not
  change.
- **`Sunlight` takes the shadows:** at a point, shaded exactly; over the
  grid, which cells the beam reaches is worked out for the sun at each
  five minutes of a run (`SHADOW_EVERY_S`) and kept, so that a probe or a
  sensor read every minute costs one test in five. The beam is all the
  light there is until P08.7, so for now what is shaded takes nothing.
- **What it costs:** 6 ms for the climate box's 2,496 cells and 32
  solids; 0.3 s for the tomato compartment's 18,432 cells and 223 solids.
- **What it does:** at 12:45 on 1 January under a clear sky, a fifth of
  the climate box's floor lies in the crop gutters' shadows, which fall
  0.9 to 1.6 m north of them under the 15° sun; a probe in the open south
  of the first row reads 417.5 µmol/m²/s, one in its shadow nothing.

### P08.6: Plants

Plants' crowns, each plant's PAR and daily light integral, the
`SunlitEnvironment`, and the inspector's PAR. PAR sensors read the field.
Visible result: two plants, one shaded and one exposed, compared in the
inspector. Tests: a shaded plant's PAR is less; a plant grown in its own
light grows less where it is shaded.

#### As implemented

- **The solar lab** (`solar_lab`) comes in this step, for its visible
  result: the climate box's house, shut, on 20 March 2026 under the cold
  spring day without a cloud; one row of 16 plants along the middle on a
  crop gutter; a stack of crates 1.5 m high just south of its first four
  plants; PAR sensors 0.3 m up in the sun south of the crates and in their
  shade north of them; and a heater, off, so that it has a climate run.
  Its plants are all of one height: a scenario's crop starts alike, so
  the crates, not the plants' heights, make the shade. Its reference
  baseline is recorded.
- **`solar.plants`:** `Crown`, a cylinder 0.25 m across about each plant's
  visible stem at its planting position; `crowns(...)` from a scenario's
  plants; `PlantLight`, each plant's PAR, the mean on a level surface at
  its crown's top, at its middle and six points halfway out, and its
  daily light integral, by the trapezoid rule every ten minutes;
  `SunlitEnvironment`, the plant model's `Environment` with each plant's
  own daily light integral and the rest of its day from another.
- **The crowns shade:** `Shadows.of` takes them beside the structure and
  the fixtures, so that a scenario's climate field, its probes and its
  sensors are shaded by its plants too.
- **`services.sunlight`:** a scenario's sunlight and its plants' light,
  kept for each layout and weather, the same object the climate run's
  field is lit by; `GET /api/scenarios/{id}/climate/plants?t=` gives each
  plant's PAR then and its first day's light integral. `air_grid` moves
  to `services.grid` and `LONGEST_RUN_S` to `climate.day`, for the field
  service and this one to share.
- **PAR sensors read the field's PAR,** as the other sensors read theirs;
  the climate box's reads nothing at night.
- **The viewer:** with a plant selected in a climate run's view, the
  inspector gives its PAR now and its day's light. The scenario table's
  rows lose their 1 px of padding, so that the info panel keeps a fifth
  scenario in the usual window.
- **What it does:** at the equinox's noon the crates leave the first four
  plants none of the beam, which is all the light until P08.7, and the
  others take 1094 µmol/m²/s; through the day the shaded ones take 2 to
  7 mol/m²/d against 27 in the open; grown ten days in their own light,
  a shaded plant's organs grow less than an exposed one's.

### P08.7: The diffuse sky and the clouds

The Erbs split into beam and diffuse, the diffuse sky's transmission and
structural shading, and the clouds' dimming, with the QA override.
Visible result: the cloud slider softens the shadows and dims the whole
floor. Tests: under full cloud nearly all is diffuse; the total falls with
cloud.

#### As implemented

- **Erbs's split** (`solar.sky.diffuse_share`) replaces the beam-only one:
  a clear equinox noon's light is a fifth the sky's, a dark sky's nearly
  all of it. The beam still never carries more than the sun gives above
  the atmosphere. Erbs's published polynomial dips 0.0007 below its 0.165
  floor just short of k_t = 0.8; it is left as published.
- **Kasten and Czeplak's clouds** (`cloud_factor`) dim a synthetic day's
  clear sky: half clouded passes 93%, full a quarter. The cold spring
  day, half clouded, now gives 7% less light than in P08.3 to P08.6.
- **The clouds' QA override:** a weather's name may end with `@` and a
  cloud cover, `cold_spring_day@80` or `default@100`, which every service
  and every kept run then keys by, as it does any weather; the scenario
  keeps it as `cloud_cover_pct`, and its run's weather is wrapped
  (`weather.sources.Clouded`) so that its radiation goes from what its own
  clouds pass to what these would. A cover beyond 0 to 100 % is refused.
- **The sky's light inside** passes the glass (0.773) and the roof's
  structure, the share of the house's plan its rafters and gutters cover
  (`solar.shadows.roof_shading`): 5% for the climate box, 7% for the
  tomato compartment. It reaches every point inside alike, the shade of
  fixtures and crowns among them.
- **The viewer:** the Weather panel gains a cloud slider (`&clouds=80` in
  the address; "Its own" gives the weather its clouds back), and its light
  says how much of it is the sky's. The scene's sun is as strong as the
  beam's share of the light, and the sky's ambient light brightens as it
  falls, so that under full cloud the shadows all but go.
- **What it does:** at the equinox's noon in the solar lab, the plants
  behind the crates take 198 µmol/m²/s, the sky's light, against 1069 in
  the open; under a full sky of cloud, 238 against 243.

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
  not traced ray by ray: what stands inside, fixtures and crowns, does not
  shade it.
- **A plant's crown is a cylinder,** not its leaves; the plant lab's
  organ-level leaves do not cast shadows on each other yet. The crowns
  stand as tall as on the run's first day through every later one.
- **The glass is clean and dry:** no condensation or dirt on it.
- **A beam crosses the glass once:** one leaving one span's roof and
  crossing the next span's is passed as if through one pane; open vents
  and doors pass the beam as their glass would.
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
