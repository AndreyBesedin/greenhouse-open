# P06: Virtual sensors and the observation layer

**Status:** in progress: P06.1 and P06.2 done, P06.3 next. Part of the
[simulator roadmap](README.md).

## Goal

Make the simulator observable through the same imperfect sensor abstraction
that integrations with real greenhouses will use.

## Dependencies

P00 (the viewer) and P04 (environment fields). P01 and P02 give sensors a
place to stand. P05's climate run gives them air that changes in seconds.
Cameras benefit from P03's plants, but don't need them.

## Direction

- **Sensors sample truth, and emit observations.** A sensor reads the world
  where it stands, at its cadence, and reports what an instrument would:
  - with noise, bias and drift;
  - with gaps, and late.

  Nothing a policy reads leads back to the truth itself.
- **Truth leaves by its own path.** As the simulator already does for its
  daily readings (`greenhouse_sim.ground_truth`), what is really the case is
  available to evaluation and QA tooling only, never through the
  observation API.
- **One observation contract, whatever the source.** A simulated reading
  should look like a real one, so that the same policy or analysis runs on
  either.
- **Imperfections are data, and seeded.** How a sensor errs is part of its
  configuration, and the same run always errs the same way.

## Design

Today the simulator has one sensor model: the daily engine's
`SimpleSensorModel`. Each simulated day it reports one noisy greenhouse air
temperature, and, for every plant, noisy soil moisture, fruit counts, ripe
mass and visible height, as `greenhouse_protocol.Observation` records. It
has no placement, no cadence below a day, and no sensor identity: a reading
says what it measures, not which instrument measured it.

P06 adds sensors that stand somewhere and read the air a climate run (P05)
computes, second by second, and cameras that see the scene. The daily
sensors stay as they are, on the crop's clock. Joining the two clocks is
P09's.

### 1. Sensors: kinds, placement and configuration

- **Vocabulary:** `domain.sensors.SensorKind`:
  - **point sensors:** temperature, humidity, CO₂, air velocity (an
    anemometer) and PAR;
  - **cameras:** an RGB camera, with depth and instance passes.
- **Placement:** as equipment is (P05), a sensor is placed in a scenario's
  layout file, beside its fixtures and equipment. It has an identifier, a
  kind and a pose: a point sensor its position, a camera its position and
  the point it looks at.
- **Configuration**, on each sensor:
  - **its cadence:** a sample every so many seconds;
  - **its units,** and a quantization step;
  - **its imperfections** (section 3).

  A camera adds its intrinsics, as the protocol already describes a real
  camera's (`greenhouse_protocol.sensor.CameraIntrinsics`): its image size,
  focal lengths and principal point.
- **In the scene:** a sensor is an entity of its kind, small and
  selectable. The inspector shows its configuration. A camera shows its
  frustum.

*Alternatives:*
- **Sensors in the scenario's configuration**, rather than its layout:
  possible, but they are placed like equipment, and another layout may
  instrument the house differently.
- **Sensors only in the viewer:** simpler for the QA scene, but then the
  simulator could not produce observations headless, for a policy or a
  batch run.

### 2. What point sensors read

A point sensor samples the scenario's air where it stands, by the field's
own trilinear interpolation (`EnvironmentField.sample`):

- **the source:** the climate run, for a scenario with equipment, at the
  sample's moment; for any other scenario, its own airflow, which is steady;
- **what each kind reads:**
  - a temperature sensor, the air's temperature;
  - a humidity sensor, its relative humidity;
  - an anemometer, its speed;
- **CO₂:** a climate run carries no CO₂ yet. It is carried as the run's
  third scalar, beside temperature and water: uniform at the
  outside's 420 ppm to start, exchanged through open vents. With no source
  or sink yet, it stays uniform, but a CO₂ sensor reads the field like any
  other, and a later dosing actuator or the crop's uptake changes it. It
  costs little: the transport already carries two scalars in one array.
- **PAR:** no model gives the light yet (P08). A PAR sensor stands, is
  configured and reports, but each of its observations says the quantity
  is unavailable, rather than inventing a value.

### 3. Imperfections

Each sensor's configuration says how it errs:

- **noise:** Gaussian, of a standard deviation;
- **quantization:** readings rounded to a step;
- **bias:** a fixed offset;
- **drift:** an offset growing linearly with time since the run's start;
- **dropout:** each sample missing with a probability;
- **latency:** each reading delivered a fixed time after its sample.

The sensor's random draws are seeded by the scenario's seed, the sensor's
identifier and the sample's index. So:
- a reading is the same however the run is asked for, in whatever order;
- two sensors never share their noise;
- adding a sensor changes no other sensor's readings.

A clean sensor (everything zero) reports the truth, interpolated, exactly.

### 4. The observation contract

A simulated observation should carry what a real one would, plus nothing
that gives away the truth:

- **which instrument:** the sensor's identifier;
- **when:** the moment it was sampled, and the moment it was delivered;
- **what:** the quantity, its unit, and its value, or none if missing;
- **its quality:** what is known of the reading, such as being clipped at
  its instrument's range. A dropped sample, or a quantity no model gives,
  is no reading at all, and staleness is the log's to say (section 5);
- **provenance:** the run that produced it.

The protocol's `Observation` has the time, the quantity, the value and the
source, but not the instrument, the delivery time or the quality. Two ways
to carry them:

- **Extend the protocol's `Observation`** with optional `sensor_id`,
  `delivered_at` and `quality` fields. They are not a simulator's
  peculiarity: a real greenhouse's readings have instruments, delays and
  gaps too. Old records stay valid.
- **Keep a simulator-only reading,** mapped onto the protocol's
  `Observation` where a canonical record is needed, the extra fields
  dropped.

The first is chosen. It keeps one schema for simulation, historical replay
and live ingestion, which the roadmap asks for.

### 5. The observation log and the truth beside it

- **The log:** for a climate run, every sensor's observations up to a
  moment, in delivery order, append-only:
  - `GET /api/scenarios/{id}/climate/observations?…&t=600`: asked as the
    climate field is (levels, schedule, openings);
  - a reading delivered after `t` is not in it yet, though sampled before.
- **Freshness:** each sensor's latest delivered reading, and whether it is
  stale.
- **The truth, apart:** `GET /api/scenarios/{id}/climate/truth?…&t=600`
  gives what each point sensor would read if it were perfect, at each of
  its samples. It is for QA and evaluation, and lives beside the
  evaluation tooling, not the observation API. A test checks, as one does
  today for the daily ground truth, that nothing on the observation path
  imports it.

### 6. Cameras

The viewer already draws the scene in WebGL. A camera is drawn by the same
renderer, from its pose, with its intrinsics, into a panel beside the main
view:

- **RGB:** the scene as the camera sees it;
- **depth:** each pixel's distance from the camera, in metres, as a
  greyscale;
- **instance:** each pixel coloured by the entity it shows, with the
  entity's identifier recovered from the colour; the panel lists the
  entities in view, and how many pixels each covers.

A camera's frame is drawn on demand from the scene and the camera, so it is
deterministic and needs storing nowhere. The observation log records a
camera's frames as metadata: its sample moment, pose, intrinsics and image
size. A headless renderer that writes images for datasets (Blender and
BlenderProc, say) is later work behind the same camera contract.

The projection is plain pinhole geometry, written once in Python and once
in TypeScript and tested against each other: a known point at a known
place lands on a known pixel.

*Alternatives:*
- **Render in Python** (offscreen OpenGL, or a ray caster): headless from
  the start, but a second renderer to own, and slow for an early project.
- **Store frames:** reproducible anyway, so unnecessary until datasets
  need them.

### 7. Viewer

- **Sensors in the scene,** each selectable, with its configuration in the
  inspector. A camera shows its frustum.
- **A selected point sensor:**
  - **its readings:** the latest reading and its quality;
  - **the truth beside it,** in a QA-only panel;
  - **a chart of both through the run,** the reading drawn as it
    arrived, gaps and all.

  The charts are plain SVG, as P05's probe charts.
- **Imperfections on and off:** a QA switch shows every sensor as if
  clean, to see what its imperfections do.
- **A selected camera:** its panel with RGB, depth and instance tabs, and
  its frames' history.

### 8. Scenarios

- **`climate_box` gets sensors:** a temperature and humidity sensor in each
  half of the house, an anemometer in the fan's jet and a CO₂ sensor. They
  watch P05's equipment act.
- **A new `sensor_lab` scenario,** small, for P06's QA:
  - **a known temperature gradient:** a prescribed airflow whose
    temperature rises linearly along the house;
  - **a clean sensor and an imperfect one** side by side;
  - **a camera** looking along the house at boxes that partly hide one
    another.

*Alternative:* a `sensor_lab` layout of the climate box instead of a new
scenario. It would share the box's still air and equipment, but a known
gradient needs its own base airflow, which is a scenario's.

## Steps

| Step | Commit summary | Status |
| --- | --- | --- |
| P06.1 | `feat(sensors): define sensor and observation contracts` | Done |
| P06.2 | `feat(sensors): add point environment sensors` | Done |
| P06.3 | `feat(sensors): add noise, bias, drift, dropout and latency` | Planned |
| P06.4 | `feat(cameras): add a virtual RGB camera and its frustum` | Planned |
| P06.5 | `feat(cameras): add depth and instance passes` | Planned |
| P06.6 | `feat(observations): add the observation log and history charts` | Planned |
| P06.7 | `test(sensors): add the sensor lab, its occlusion and noise` | Planned |

### P06.1: Sensor and observation contracts

Sensor kinds, placement in layout files, configuration (cadence, units,
imperfections, a camera's intrinsics); the observation contract (section
4); sensors in the scene. Visible result: sensors stand in the climate box,
and the inspector shows a selected one's configuration. Tests: layouts
refuse sensors outside the house or sharing an identifier; observations
pass the protocol's conformance checks.

#### As implemented

- **The protocol's `Observation`** gains optional `sensor_id`,
  `delivered_at` and `quality`. Records that leave them unset are written
  exactly as before: an unset field is left out of the JSON.
  - **A gap is an absent record,** as the protocol already rules. A
    dropped sample is no observation, and a PAR sensor with no light to
    read reports none. So `quality` marks readings that exist: so far
    `CLIPPED`, a reading held at the end of its instrument's range.
  - **The conformance checks** refuse a delivery before the reading or
    without a timezone, and an empty sensor identifier.
  - **A new observation type,** `AIR_SPEED_M_S`, is an anemometer's
    reading.
- **Sensors in a layout** (`world.sensors`):
  - **a point sensor:** its kind, position, cadence (60 s by default) and
    imperfections, all nothing for a clean one, in its unit;
  - **a camera:** its position, target and the protocol's
    `CameraIntrinsics`, its frame turned so that its picture is upright.

  Housings are in the way of nothing; sensors must stand inside the house,
  with identifiers of their own.
- **The climate box is instrumented,** clean for now:
  - temperature and humidity in each half of the house, side by side
    1.5 m up;
  - an anemometer in the fan's jet;
  - CO₂ in the middle and PAR under the roof.
- **The scene** (schema 15): `SENSOR` and `CAMERA` entities, their
  configuration in their properties, a legend of their own in the
  categories view. The box's scene: 121 entities.

### P06.2: Point environment sensors

Temperature, humidity, CO₂ (carried by the climate run), air velocity and
PAR (unavailable until P08), sampling the climate run or the scenario's
own air. Visible result: selecting a sensor shows its reading beside the
air's true value, in a QA-only panel. Tests: a noise-free sensor matches the
interpolated field within tolerance; CO₂ stays uniform with nothing to
change it, and its budget closes.

#### As implemented

- **CO₂ in the climate run:**
  - **carried** as its third scalar, beside temperature and water, in the
    same pass;
  - **starts** uniform at the scenario's starting CO₂, the outside having
    its own, both 420 ppm unless set;
  - **exchanged** through open doors and vents.

  The climate field publishes it as `co2`; every probe shows it.
- **Point sensors** (`sensors.air`): each takes a sample every cadence from
  a run's start, of its quantity where it stands, as the field samples it
  there:
  - temperature, relative humidity, CO₂, or an anemometer's speed;
  - PAR, which no model gives, is no reading at all.
  - **The air sampled:** a climate run's, for a scenario with equipment;
    otherwise its own airflow, the same at every moment.
  - **The run's clock:** it starts at its scenario's start date's midnight,
    UTC, until P09 joins the clocks.
- **Observations:** each reading is a protocol `Observation` naming its
  sensor and its run, in the order delivered.
  `GET /api/scenarios/{id}/climate/observations?…&t=600` serves them,
  asked as the climate field is.
- **The truth, apart** (`evaluation.sensor_truth`): what each sensor truly
  sampled, served by `GET /api/scenarios/{id}/climate/truth?…`.
  - **Guarded:** a test checks that only evaluation and the services
    serving it import the truth, this one and the daily one alike.
  - **A stale note fixed:** the daily ground truth's note had said such a
    test existed; it didn't, until now.
- **The viewer:** a selected point sensor shows its latest reading at the
  moment drawn, and, in a panel marked "Truth, for QA only", what it truly
  sampled then. In the climate box, ten minutes into a heated run, the back
  temperature sensor reads 18.59 °C, as the truth is.

### P06.3: Imperfections

Noise, quantization, bias, drift, dropout and latency, seeded per sensor
and sample. Visible result: a chart shows the truth and the imperfect
reading diverging over the run. Tests: the same seed gives the same
readings in any order; a sensor's noise has the configured mean and spread;
dropout's rate and latency's delay are as configured.

### P06.4: A virtual RGB camera and its frustum

A camera's pose and intrinsics, its frustum in the main view, and a panel
drawing what it sees. Visible result: the main view shows the camera and
its cone; the panel shows exactly what it sees. Tests: a known object at a
known place projects to the expected pixels, in Python and in the viewer
alike.

### P06.5: Depth and instance passes

Depth and instance passes from the same camera, the entities in view and
their pixel counts, kept apart from the RGB frame. Visible result: tabs show
RGB, depth and instance views from one camera. Tests: an entity selected in
the main view is the one the instance pass names at its pixels; depth at a
known surface is its distance.

### P06.6: The observation log and history charts

The log, freshness and history, through the API and the viewer. Visible
result: selecting a point sensor shows its chart through the run;
selecting a camera shows its frames' metadata. Tests: the log is
append-only and in delivery order; a reading appears only once delivered;
a sensor is stale exactly when it should be.

### P06.7: The sensor lab

The `sensor_lab` scenario (section 8): a known gradient, a clean and an
imperfect sensor, a camera and occluders. Visible result: the final QA's
scene. Tests: the clean sensors read the gradient exactly; the imperfect
one's errors are what its configuration says.

## Final QA: `sensor-lab`

At runtime:

- inspect the sensors' placement;
- compare readings with the truth;
- switch noise, drift and dropout off and on;
- inspect the camera's frustum;
- compare its RGB, depth and instance views;
- move an obstacle in front of the camera and see it hide what is behind;
- check the observations' timestamps and cadence.

Expected:

- clean sensors read the truth;
- imperfect ones err as configured, the same way every time;
- the camera's views agree with one another and with the main view;
- what is hidden from the camera is missing from its instance pass.

## Acceptance criteria

- [ ] Sensors emit observations, not references to the world's state.
- [ ] Environmental sensors sample spatial fields.
- [ ] The browser camera produces at least RGB, depth and instance identity.
- [ ] Noise and timing imperfections are reproducible.
- [ ] The observation history is usable by later policies.

## Known approximations

What P06 simplifies on purpose, kept here until a later step removes it:

- **Drift is linear in time.** Real sensors' drift is often a random walk,
  wandering rather than climbing steadily. A random walk, seeded as noise
  is, would be closer to them, at the cost of tests that can only check its
  spread, not its value.
- **PAR is unavailable** until P08 models the light.
- **Cameras are drawn in the browser:** a headless renderer that writes
  images for datasets comes later, behind the same camera contract.

## Review decisions (8 October 2026)

1. **The observation contract:** extend the protocol's `Observation` with
   optional `sensor_id`, `delivered_at` and `quality` fields.
2. **CO₂:** carried by the climate run now, uniform until something changes
   it.
3. **Cameras:** drawn in the browser, their frames logged as metadata;
   headless image generation later.
4. **The QA scenario:** a new `sensor_lab` scenario.
5. **Drift:** linear. A random walk is recorded as a possible improvement
   (Known approximations).
