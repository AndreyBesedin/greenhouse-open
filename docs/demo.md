# The simulator's demo: the reference greenhouse

A guide to running the simulator and its viewer on your own machine, and to
walking through the reference scenario, `reference-greenhouse-v1`, as the
[P09 roadmap](roadmap/p09-integrated-scenario.md) checks it: what each step
should show, what the simulator simplifies, and what to do when something
does not start.

## What you need

- **Python 3.14 or newer**
  ([decision 0003](decisions/0003-require-python-3-14.md)).
- **Node 24 and npm**, for the viewer
  ([decision 0008](decisions/0008-build-the-viewer-with-npm-node-24-and-vite.md)).
- **A browser with WebGL**, on a machine with a graphics card for a smooth
  view. No other service is needed, and nothing leaves the machine: the API
  answers on the loopback interface only.

## Set it up once

From a clone of the repository:

```bash
python3.14 -m venv .venv && source .venv/bin/activate
python -m pip install -e ./greenhouse_protocol -e ./greenhouse_sim
cd greenhouse_sim/web && npm ci && cd ../..
```

## Start it

```bash
python scripts/demo.py
```

One command starts the simulator's local API on port 8765 and the viewer's
development server on port 5173, waits until both answer, and opens the
reference greenhouse in the browser, at noon on its opening day. Ctrl+C
stops both; so does either stopping. `--no-browser` leaves the browser
closed, and `--api-port` and `--viewer-port` move them.

## The reference scenario

`reference_greenhouse` (its manifest, with a note on every choice, is
`greenhouse_sim/greenhouse_sim/scenarios/manifests/reference_greenhouse.json`):

- **The house:** a small Venlo-style house of three 3.2 m spans and three
  4 m bays, 4 m to the gutters, near Amsterdam; a roof vent along each
  span's ridge and a door in the front gable.
- **The crop:** 32 cherry tomatoes in four rows of eight, grown organ by
  organ from transplants, each plant's traits drawn from seed 42, on a
  high-wire double row lowered every week and harvested every week.
- **The equipment:** two fans over the front path blowing down the house, a
  15 kW heater, a dehumidifier; temperature, humidity, CO₂ and PAR sensors,
  an anemometer, a weather station outside, and a camera looking down the
  middle path.
- **The season:** 120 days from 1 March, the cold spring day's weather
  every day under the season's own sun, the heater, vents and fans on a
  fixed daily schedule.
- **The opening day:** day 80, the first with a red fruit, kept as a
  checkpoint beside the manifest so that the viewer opens there in seconds
  rather than working out 80 days.

## The walk-through

The final QA of P09, step by step. The numbers are the simulator's own, from
its tests and its golden views (`tests/test_reference_qa.py`).

1. **Start it and open the reference scenario, seed 42.** `python
   scripts/demo.py` opens it at noon on day 80; the scenario list says its
   seed and its opening day, and in QA mode (step 7) the run's manifest
   names the seed, the manifest's version and the commits of the simulator
   and the viewer.
2. **The house and the crop's layout.** "Dimensions and axis labels", in
   the display options, measures the house, 12 × 9.6 m. A click on anything
   selects it, and the inspector names it and its size; the rows stand 1.6 m
   apart about the middle, the plants 0.75 m apart along them.
3. **Morning to noon: the sun, the shadows and the radiation.** "Climate
   run" moves through the day. At 6:00 the sun stands 10° up in the
   east-north-east, the crop's shadows long on the floor; at the sun's noon,
   12:40 on the run's clock (its site's standard time), 58° up in the south.
   "Air field" set to a slice of PAR shows the light in the canopy, with
   the gutters' shadows across it.
4. **The air: vectors, temperature and humidity slices.** The climate's
   field drawn as arrows shows the fans' two jets down the house, 1.4 m/s
   at the anemometer at noon; as a slice, its temperature or humidity
   across or along the house.
5. **The fans, the heater and the dehumidifier.** The Equipment panel
   switches each; the field and the house's air follow, from the moment of
   the change. The heater warms its corner first; the dehumidifier dries
   the air around it.
6. **A roof vent, and the wind.** The schedule opens the roof vents by the
   clock: shut until 9:00, half open, then fully from 11:00, and shut again
   at 20:00. Shut at noon, the vents leave the house at 38.5 °C against
   29.5 °C open (the golden views' `vents-closed` and `vents-open`). The
   Openings sliders set how far a door or vent stands open from the run's
   start: on a later day that is another house, its season worked out
   afresh (see Troubleshooting). "Weather" overrides the wind's direction
   (`&wind=90`) and the sky's clouds (`&clouds=80`), the rest of the
   weather unchanged; that too is another run.
7. **The sensors against QA mode's truth.** "QA mode", in the display
   options (`&qa=1`), alone asks the simulator for the truth: a selected
   sensor then charts its readings against what was truly there, and a
   switch reads it as a clean sensor. The back temperature sensor is
   biased, noisy and late; a dropped sample leaves it stale until the next
   comes. QA mode's "Developer" panel says what every process holds at the
   moment, and selects a sensor or a camera from its list, easier than in
   the view once the crop is grown; QA mode also labels every plant with
   its identifier and its day's light.
8. **The fixed camera: RGB, depth and instance.** Select the camera over the
   front path, or `path_camera` in the developer panel: its panel draws what
   it sees, with tabs for its depth and its
   instance pass, and reads, under the pointer, what each pixel shows and
   how far ahead.
9. **The crop, accelerated: its seeded variation, its fruit ripening.**
   "Climate run" moves a day at a time, or plays a day a step. No two
   plants are alike, each drawn from the seed; a selected part of a plant
   charts its days, the air and its own light on each, and its fruit
   reddens as it ripens. The first red fruit, on day 80, hangs on plant 30's
   first truss.
10. **A harvest, in the plant's history.** The weekly round picks every red
    fruit: on day 84 it picks plant 30's first, 85 g, and the plant's days
    list it among what was picked. The plant lab (`?plants=lab`) harvests a
    chosen fruit by hand, and its plant's history keeps it too.
11. **A checkpoint, a branch, two schedules compared.** "Checkpoints", under
    the timeline, saves the start of the moment's day; a command given after
    it is a branch, and "Compare" charts the checkpoint's run beside the
    branch, the house's air, a sensor's readings and a plant's days, the one
    solid and the other dashed. A checkpoint downloads as JSON, and uploads
    again.
12. **Seed 42 again, against the reference.** The golden views,
    `/qa/reference-greenhouse?view=noon` and its twelve others, draw the
    reference run from the repository's kept file, with their state probes;
    CI compares their screenshots with `e2e/visual/__screenshots__`, and
    `python greenhouse_sim/tests/test_reference_qa.py --measure` works the
    probes out afresh, to compare with those the test keeps.

## What the simulator simplifies

Gathered from every project's own list; each is a choice, kept until a later
step removes it.

**The air and the climate** (P05, P07):

- The house's air through a run is one well-mixed volume; the air cell by
  cell is drawn for a moment when asked, from an hour of air started from
  the house's, not kept through the season.
- The flow inside is the nearest conserving one, not a solved one: the base
  airflow and the fans' jets, without momentum of its own or buoyancy. A
  fan's jet is a free jet, which turns at no wall.
- Condensation's latent heat is not counted; a dehumidifier takes its
  rating whatever the air.
- The glass has no heat capacity; the floor and the ground pass no heat.
- Pressure coefficients are tabulated for low-rise buildings, an opening is
  a point at its centre's height, and infiltration is spread evenly over
  the envelope.

**The sun** (P08):

- No light reflected from the ground or inside the house; the diffuse sky
  is isotropic, shaded by the structure as a whole.
- The glass is clean and dry, and a beam crosses it once.
- The sun's heat goes to the air at the floor by a fixed share.

**The crop** (P03, P09):

- Its air is the house's, the same for every plant; only its light differs
  from plant to plant, read at its crown's top.
- It changes nothing in the air: no transpiration, no CO₂ uptake, and its
  water status is always 1.
- The house sees the crop as it stood before its first day, for the sun's
  heat in its air and the PAR sensors' light.
- Its days couple at their ends: a day's growth takes that day's air and
  light, and a crown's height changes the light the next day.
- A lowered crop's stems lie along one line on each gutter edge, without
  twine or hooks.
- The live stream grows every scenario with the simple daily model.

**The sensors and the camera** (P06):

- A sensor's drift is linear in time.
- The camera is drawn in the browser, its frames perfect in time and image;
  its depth and instance passes see through glass.

**The run** (P09): checkpoints are kept at a day's start only, in the API's
memory until it stops.

## Troubleshooting

- **A port in use.** `scripts/demo.py` says which: stop what holds it, or
  pass `--api-port` or `--viewer-port`. The browser tests use their own API
  on 8766 and previews on 4317 to 4319, apart from the demo's.
- **The wrong Python or Node.** The demo checks both before it starts, and
  says which it needs: Python 3.14 or newer, with greenhouse-sim installed
  for it, and the Node version `greenhouse_sim/web/.nvmrc` names.
- **The viewer's packages missing.** `npm ci` in `greenhouse_sim/web`.
- **A slow first answer.** Opening day 80 is quick, from its kept
  checkpoint. A moment beyond it is worked out from there, about 2.5 s for
  each simulated day; the season's end takes minutes the first time, and
  the HUD says how long the simulator took for the latest request. Another
  weather, the wind or the clouds overridden, or a door or vent set open
  from the start with its slider, makes another run, which the kept day
  does not fit: it is worked out from the season's start, minutes too. A sensor selected late in a day reads its log from the
  day's start, each reading sampling the house's whole field: at noon,
  minutes in QA mode.
- **A jerky view.** Without a graphics card the browser draws in software;
  the HUD's frame rate says so.

## Recording the demo video

The walk-through is also a browser test, `greenhouse_sim/web/e2e/demo.spec.ts`,
which CI runs after the other day-by-day tests. On a machine with a
graphics card, with the viewer's packages installed:

```bash
cd greenhouse_sim/web && PYTHON=../../.venv/bin/python npm run demo:record
```

plays it with a caption on each step, lingering on each, and records it as
video under `test-results/demo/`, so that each release can record it
again. GitHub plays a video in the README only when it hosts it, an MP4 or
WebM uploaded through an issue or a pull request, under 10 MB: the README
plays a short cut, and links a longer one. Uploading them is done by hand.
