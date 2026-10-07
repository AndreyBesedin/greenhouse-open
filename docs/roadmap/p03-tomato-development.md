# P03: Stochastic tomato development and procedural plant geometry

**Status:** in progress. Part of the [simulator roadmap](README.md).

## Goal

Build our own tomato development model: organ by organ, stochastic and
longitudinal, inspired by functional-structural plant modelling but not
dependent on any of its frameworks, with plant geometry generated from the
plants' biological state.

## Scope

Tomato's main stem only, at first: phytomers, internodes, coarsely
represented compound leaves, trusses, flowers and fruits. No cellular model,
no detailed roots and no deformable mechanics.

## Position on external plant libraries

GroIMP, OpenAlea and CPlantBox are not runtime dependencies. They, the
papers around them and the crop-modelling literature are sources for state
variables, thermal-time formulations, source and sink ideas, organogenesis
rules, parameter ranges and validation targets. Our implementation optimises
for longitudinal identity, stochastic populations, easy integration with the
greenhouse's environment, browser-friendly geometry, deterministic replay and
future parameter fitting.

## Direction

- Every visible organ has a persistent identity, derived from where it sits
  in the plant, so it is the same organ from one day to the next and from one
  run to the next.
- Randomness comes from one seed, the simulation's. Each draw's generator is
  derived from it and a hash of who draws and what for: the plant, then the
  organ if it is an organ's own draw, then the process. So one plant's or
  organ's draws never depend on another's. What is hashed is the drawer's
  identifier, which never changes, not its state, which does.
- Biological state drives geometry and appearance: the viewer draws what the
  model's organs say, never the other way round.
- The plant takes its environment through an explicit interface, so the
  simple climate today and spatial fields later (P04) serve it alike.

## Starting point

`greenhouse_sim` has a simple daily tomato model (`biology/tomato/simple/`):
whole plants with a stem length, trusses and fruits, behind the plant-model
contract (decision 0006), and drawn in the viewer as one cylinder per plant.
P00 gives the viewer, P02 the planting positions plants stand at.

## Clean-up

What the reviews of P03's pull requests leave for the end of P03 is collected
in [the P03 clean-up](p03-cleanup.md), done in one pass once its steps are
merged.

## Steps

| Step | Commit summary | Status |
| --- | --- | --- |
| P03.1 | `feat(plants): define plant topology and organ state schema` | Done |
| P03.2 | `feat(plants): procedural stem, internode and leaf geometry` | Done |
| P03.3 | `feat(plants): add thermal-time organogenesis` | Done |
| P03.4 | `feat(plants): add correlated stochastic plant variation` | Done |
| P03.5 | `feat(plants): add trusses, flowers and fruit set` | Done |
| P03.6 | `feat(plants): add fruit growth, ripeness and colour` | Done |
| P03.7 | `feat(plants): consume local environment inputs` | Planned |
| P03.8 | `feat(plants): add pruning, harvest and lowering actions` | Planned |
| P03.9 | `test(plants): add biological and visual regression scenarios` | Planned |

### P03.1: Plant topology and organ state schema

Identifiers for the plant, its stem (axis), phytomers, internodes, leaves,
trusses, flowers and fruits; their parent-child relationships; each organ's
birth time, thermal age and stage; and the seed hierarchy. Visible result: a
debug tree in the browser, and a schematic 3D stick plant built from the
topology. Tests: topology invariants, and deterministic identifiers.

As implemented (see [decision 0022](../decisions/0022-plant-organs-are-named-by-where-they-sit.md)):

- `greenhouse_sim.biology.tomato.organ.topology` describes a plant: its main
  stem (axis) of phytomers, each with its internode and leaf and perhaps a
  truss, whose flowers become fruits when they set. Identifiers say where an
  organ sits (`p01_n05_leaf`, `p01_t02_fl04`, `p01_t02_fr04`), every organ
  records the plant's thermal time when it appeared, and leaves, flowers and
  fruits have stages. `topology_problems` lists whatever breaks the
  structure's rules: identifiers used twice or named for another place,
  phytomers out of order, organs older than what bears them or appearing
  after the plant's thermal time, and a flower with a fruit unless it set.
- `seeds` gives every draw a generator from the seed hierarchy: simulation,
  plant, organ, process.
- Until the model grows plants (P03.3), `reference.young_plant` builds a
  young plant by hand: nine phytomers a phyllochron apart, the first truss on
  the ninth with six flower buds. `geometry.organ_geometry` derives its stick
  plant: internodes stacked up the stem, each leaf and truss a stick from its
  node turning by the golden angle, flowers and fruits as spheres along their
  truss, all in the plant's own frame.
- The organ model is not yet one of the engine's plant models: it is built
  and shown in a plant lab (decision 0022), a service
  (`greenhouse_sim.services.plants`) behind `GET /api/plants/scene` and
  `GET /api/plants/structure`. P09 connects it to the engine.
- The scene gains a `sphere` shape and `INTERNODE`, `LEAF`, `TRUSS`, `FLOWER`
  and `FRUIT` kinds, so its schema moves to version 12. Each organ's entities
  say which organ they are, its parent, its thermal age and its stage.
- The viewer's plant lab (`?plants=lab`, and a button beside the gallery)
  opens close to its plant and shows its structure as a debug tree: every
  organ with its kind, thermal age and stage. An organ chosen in the tree is
  selected in the view, and one clicked in the view is the organ the tree
  names.
- Tests:
  - Python: the reference plant keeps every rule; organs are named by where
    they sit and name their parents; identifiers are the same on every build;
    thermal ages; six kinds of broken structure are found out, and phytomers
    out of order or repeated; draws follow the seed hierarchy; internodes
    stack at their lengths, leaves reach from their nodes as long as the
    leaf, a truss's flowers hang along it, and every shape belongs to an
    organ; the scene places each organ where the plant stands and says what
    it is; the lab answers with its scene and structure.
  - Viewer: the structure is read into a tree from the plant down, with each
    organ's development and stage and whether it is drawn, and a structure
    that cannot be read is refused.
  - Browser: the lab draws the stick plant, its tree lists every organ, a
    leaf chosen in the tree is selected, and an internode clicked in the view
    is selected with its thermal age.

### P03.2: Procedural stem, internode and leaf geometry

Internodes as cylinders along the stem, simplified leaves (a petiole and
leaflets), phyllotaxis, and organ transforms derived from the topology.
Visible result: a recognisable young tomato plant generated only from
biological parameters. Tests: geometry dimensions correspond to organ state.

As implemented:

- Each leaf is a tomato's compound leaf, coarsely. A petiole leaves its node,
  then the rachis's segments bear a pair of leaflets at each joint and a
  terminal leaflet at the tip, all together as long as the leaf. The leaf
  rises from its node and each segment bends further down than the last: in
  all, a full-grown leaf droops by a set angle, and a shorter one in
  proportion to its length. Leaflets are flat ellipsoids lying in the leaf's
  plane, growing towards the tip, the lateral ones spreading from the rachis
  at a set angle. Successive leaves turn by the golden angle, as before.
- The stem's internodes are drawn as long and as thick as they are. The
  reference plant's three youngest phytomers are still growing, each in
  proportion to its thermal age, so the plant tapers to its tip.
- How the organs are proportioned and held is the plant's form
  (`PlantForm`): leaflet pairs, the terminal leaflet's and the petiole's
  shares, leaflet sizes and aspect, the leaflets' spread, the leaf's
  insertion angle and droop, and the rachis's thickness. It has a tomato's
  typical values, and P03.4 varies it from plant to plant.
- Every shape names its organ and its part (`internode`, `petiole`, `rachis`,
  `leaflet`, `truss`, `flower`, `fruit`), and so does its entity.
- The scene gains an `ellipsoid` shape, so its schema moves to version 13.
  The viewer batches spheres and ellipsoids as it batches cylinders: by kind,
  shape and finish. The plant lab's 115 shapes take eight draw calls.
- Selecting any part of an organ highlights the whole organ, and marks it in
  the debug tree; choosing an organ in the tree selects its first part. The
  inspector writes sizes under a centimetre to a tenth of a millimetre.
- Tests:
  - Python:
    - internodes stack as long and thick as they are, and the youngest
      phytomers are still growing;
    - a leaf's parts join end to end, from its node to its terminal leaflet,
      and reach as far as the leaf is long;
    - leaflets are sized by their leaf, growing towards its tip, and lie in
      the leaf's plane on either side of the rachis;
    - a leaf droops in proportion to its length;
    - successive leaves turn by the golden angle;
    - a longer leaf is longer in every part;
    - the plant's form shapes its leaves;
    - every shape is a part of an organ of its kind.
  - Viewer: spheres and ellipsoids are placed and scaled as their shapes say,
    and batched by shape; a selection highlights every part of its organ.
  - Browser: the lab draws the plant's 117 entities, and a leaf chosen in the
    tree is selected by its petiole and pressed in the tree, until an
    internode clicked in the view takes its place.

### P03.3: Thermal-time organogenesis

Accumulated thermal time, phytomer appearance, internode elongation and leaf
expansion, with configurable developmental rates. Visible result: a time
slider grows one plant from transplant size to a taller vegetative plant.
Tests: a fixed environment and seed give exact organ counts at reference
dates.

As implemented:

- `organ.development` grows a plant as thermal time accumulates.
  - **Thermal time:** each day adds its mean temperature above a base of
    10 °C, counting nothing past a cap of 30 °C.
  - **Phytomers:** a plant emerges with one phytomer, and another appears at
    the top of the stem every phyllochron (33 °Cd), each when its
    phyllochron is up rather than when a step ends.
  - **Growth:** internodes and leaves appear at a small share of their final
    sizes and grow to them along a smooth S-curve of their thermal age, over
    an expansion time of 160 °Cd. A leaf is expanding until then, and mature
    after.
  - **Final sizes:** fixed when the organ appears, and recorded in its state.
    They grow up the stem from the first phytomer's, a third of the full
    sizes, to the full sizes from the tenth phytomer up.
  - **What is carried:** a removed leaf stays removed, and trusses are
    carried as they are until P03.5 grows them.
  - **Step size:** development depends on thermal time alone, so a plant
    grown in one step or day by day is the same plant.
- `DevelopmentParams` holds the rates and sizes: base and cap temperatures,
  phyllochron, expansion time, initial shares, full final sizes, and how
  they grow up the stem.
- The topology's rules gain one: an organ is never larger than it grows.
- **The plant lab runs for 60 days.** Its plant is a transplant of 230 °Cd,
  seven phytomers and about 20 cm, grown at a constant 21 °C (11 °Cd a day).
  By day 60 it has 27 phytomers and is about 1.5 m tall.
  - **API:** `GET /api/plants/scene?day=` and `/structure?day=` show any day,
    and refuse a day outside the run, or one that is not a whole number.
  - **Viewer:** a day slider (`?plants=lab&day=30`) asks for the plant on that
    day. The scene and tree on show stay until the next day's arrive. A
    selected organ stays selected from day to day, since it is the same
    organ.
  - **Camera:** the lab opens far enough out to see the plant whole on its
    last day.
- Tests:
  - Python:
    - a day's thermal time, with its base and cap;
    - a plant emerges with its first phytomer at its initial size;
    - a phytomer appears every phyllochron;
    - exact organ counts on reference days of the lab's run (days 0, 10,
      30, 60);
    - one step or day by day give the same plant;
    - organs grow and mature, but never shrink or grow young, and every day's
      plant keeps the structure's rules;
    - the S-curve, leaf maturity and final sizes up the stem;
    - a removed leaf and a truss are carried;
    - an organ keeps its identity from one day to the next;
    - the lab's days, and the days it refuses.
  - Viewer: the address bar's day, and the structure is asked for by day.
  - Browser:
    - the lab draws day 0's plant;
    - a leaflet clicked in the view presses its leaf in the tree;
    - the slider grows the plant to day 30, keeping a selected leaf selected
      and older;
    - the slider's last day is the simulator's.

### P03.4: Correlated stochastic plant variation

A plant-level latent vigour, and variation in phyllochron, internode length,
leaf scale and orientation, drawn from seeded generators. Visible result: a
row of 20 plants that clearly varies while remaining recognisably the same
crop. Tests: the same seed reproduces geometry, different seeds change
plants, and distributions stay within their configured ranges.

As implemented (see [decision 0023](../decisions/0023-plants-vary-through-a-shared-vigour-and-keep-their-draws.md)):

- **Traits:** `organ.variation` draws each plant's traits from the seed
  hierarchy.
  - **Vigour:** a latent vigour that six factors load on.
  - **The factors:** phyllochron (−0.6, so vigorous plants develop faster),
    internode length (0.6), stem diameter (0.8), leaf length (0.8), leaf
    insertion angle (0) and leaf droop (−0.3), with coefficients of
    variation from 6% to 15%.
  - **Rotation:** a uniform turn about the stem.
  - **Limits:** every draw is held within 2.5 standard deviations, so every
    factor stays within its configured range.
- **Where they're kept:** a plant records its traits and its seed.
  Development takes the plant's phyllochron and full sizes from its traits,
  and geometry takes how it holds its leaves and where its first leaf
  points.
- **Organs:** each organ's final size varies around its plant's by 8%, drawn
  from the organ's own generator when it appears.
- **The lab's row:** 20 plants, 0.5 m apart along +y, drawn from a seed.
  - **API:** `?seed=` on its scene and structure, and `?plant=` for one
    plant's structure. A negative or wordy seed is refused, and an unknown
    plant is not found.
  - **Viewer:** a seed field and an "Another seed" button. The debug tree
    shows the selected organ's plant, and the camera looks along the row
    from its first plant.
  - **Rendering:** leaflets are drawn with fewer facets, so the row on its
    last day is about 740,000 triangles rather than 1.65 million.
- Tests:
  - Python:
    - the same seed gives the same plants, geometry and scene, while another
      seed or another plant differs;
    - a plant's draws don't depend on which other plants exist;
    - over 400 plants:
      - every factor stays within its range;
      - each spreads about 1 by its coefficient of variation;
      - each follows vigour as its loading says;
    - a spread that could vary a trait to nothing is refused;
    - traits drive development, and turn the plant and change how it holds
      its leaves;
    - organs vary around their plant, each from its own generator;
    - the lab's row varies yet stays one crop, and keeps every rule on days
      0, 30 and 60;
    - the row stands along y;
    - the lab answers for any seed and plant, and refuses what it can't.
  - Viewer: the address bar's seed, the structure asked for by plant, day and
    seed, and the plant an entity draws.
  - Browser:
    - another seed draws another row;
    - a leaflet of the third plant, clicked, brings that plant's tree.

### P03.5: Trusses, flowers and fruit set

Truss initiation rules, flower appearance, stochastic fruit set and
abortion, and stable fruit identity. Visible result: plants develop visible
trusses, flowers and small green fruits over time. Tests: fruit identifiers
persist through growth, and an aborted fruit follows an allowed state
transition.

As implemented:

- `organ.reproduction`, with `TrussParams` in the development parameters:
  - **Trusses:** a plant's first truss appears with its eighth phytomer, and
    another with every third above it, numbered from the bottom. Each draws
    its flower count, 4 to 8, from its own generator when it appears, and its
    flowers appear 8 °Cd apart from its base.
  - **Flowers:** a flower is a bud until its anthesis, 180 °Cd after it
    appears, then open. 60 °Cd later it sets fruit or aborts by its own draw:
    a truss's first flower sets with a chance of 0.9, each flower further
    along 0.05 less.
  - **Fruits:** a fruit takes its flower's place, appears when the flower
    set, at 6 mm, and keeps that size until P03.6. A young fruit aborts with
    a chance of 0.05, decided 100 °Cd after it set.
  - **Draws:** every chance is drawn once, when its moment comes, so a plant
    grown in one step or day by day sets the same fruit.
- **The topology:**
  - **States:** fruits gain an aborted stage, and a truss records how many
    flowers it bears.
  - **Changes:** each kind's allowed stage changes are stated
    (`LEAF_CHANGES`, `FLOWER_CHANGES`, `FRUIT_CHANGES`).
  - **`change_problems(before, after)`:** lists whatever is wrong with a
    later moment of a plant. Time must run forward, every organ must still be
    there, of the same kind and appearing when it did, and every stage must
    change only as allowed.
- **Geometry:**
  - **Trusses:** a truss is as long as its flowers need, 2 cm each.
  - **Flowers and fruits:** buds are small green-yellow spheres, open
    flowers larger yellow ones, and a set flower is drawn as its fruit.
    Aborted flowers and fruits have dropped, and are not drawn. The tree
    marks them as not drawn.
  - **Facets:** spheres are drawn with fewer facets, so the fruiting row on
    day 60 stays under 900,000 triangles.
- Tests:
  - Python:
    - trusses appear on their phytomers and are numbered from the bottom;
    - flower counts cover their range, and flowers appear one after another;
    - a flower is a bud, opens and is decided at its moments;
    - a set flower's fruit takes its place when it set;
    - over 150 plants, basal flowers set more than distal ones, at their
      configured chances, and young fruits abort at theirs;
    - three of the lab's plants keep every organ and change stages only as
      allowed, day after day for 60 days;
    - a fruit keeps its identifier and birth;
    - disallowed changes are found out;
    - one step and daily steps set the same fruit;
    - the lab's first plant's trusses, flower stages and fruits on days 0,
      30 and 60;
    - buds, flowers and fruits are drawn as they are, and dropped ones not;
    - buds are coloured green and open flowers yellow.
  - Viewer: an aborted flower and fruit are not drawn.
  - Browser: on day 45 the tree lists the plant's trusses, flowers and
    fruits, and a fruit chosen there is selected, under its flower.

### P03.6: Fruit growth, ripeness and colour

A fruit size and mass curve, maturity stages, a green to breaker to orange
and red appearance mapping, and a stochastic ripening offset. Visible
result: a time-lapse visibly changes fruit size and colour. Tests: ripeness
never decreases, and the drawn colour is derived from biological state.

As implemented:

- `organ.fruit` (`FruitParams`, part of the truss parameters):
  - **When it sets:** a fruit draws, from its own generator, its final
    diameter and its ripening offset. The final diameter is around 62 mm
    (about 125 g) by 8%, 4% smaller for each flower further along its truss.
    The offset is how much earlier or later than typical it starts to
    ripen, by 8%.
  - **Growth:** it grows from 6 mm to its final diameter along a smooth
    S-curve over 450 °Cd.
  - **Ripening:** it starts to ripen (breaker) a typical 480 °Cd after it
    set, scaled by its offset, and ripens to red over 100 °Cd. Its
    ripeness, from 0 to 1, never goes back.
  - **Mass and class:** its fresh mass follows from its volume, and its
    maturity class (green, breaker, turning, pink, light red, red) from its
    ripeness.
  - **Aborted fruit:** stays as it was when it dropped, however long the
    step.
- **State:** a fruit records its diameter, final diameter, mass, breaker
  time and ripeness. The fruit stage `growing` becomes `attached`: on the
  plant, growing and ripening.
- **Rules:** the topology gains two, that no fruit is larger than it grows
  and none ripens before it sets. `change_problems` adds that no organ
  shrinks and no fruit unripens.
- **Scene:**
  - **Colour:** a fruit's colour is its ripeness's, blended from green
    through yellow and orange to red.
  - **Properties:** every organ's entity reports its sizes, and a fruit its
    mass, ripeness and maturity class, so the viewer can colour by any of
    them.
- **Viewer:** the tree adds how ripe a ripening fruit is.
- **The lab's run** extends to 90 days, by which the lower trusses are red,
  and its camera sees its nearest plants whole on that day.
- Tests:
  - Python:
    - a fruit sets small and grows along an S-curve to its final size;
    - its mass follows its volume;
    - final sizes vary within their range and shrink along the truss;
    - a fruit ripens from its breaker to red and never back;
    - each fruit draws its own ripening offset;
    - maturity classes;
    - colours run from green through orange to red;
    - a drawn fruit's colour, sizes and class are its state's;
    - an aborted fruit stays as it was;
    - the lab's first plant's fruits by class and their mass on days 60, 75
      and 90;
    - shrinking and unripening are found out;
    - three lab plants are followed day by day through the whole run.
  - Viewer: a ripening fruit's ripeness in the tree.
  - Browser: a fruit followed from day 60 to the run's end turns from green
    to red and gains mass.

### P03.7: Local environment inputs

An interface for temperature, light (PAR), CO₂ and water status, with simple
first response functions; physiological realism is not yet required.
Visible result: two plants side by side under different environments
diverge in growth and ripening. Tests: a controlled perturbation gives the
expected direction of response.

### P03.8: Pruning, harvest and lowering actions

Removing a leaf, harvesting a fruit or truss, and lowering the stem and
re-anchoring its geometry, with an event log. Visible result: actions in the
browser visibly change the plant and persist through the days that follow.
Tests: harvested organs leave the attached crop but remain in the event
history.

### P03.9: Biological and visual regression scenarios

Reference plant snapshots at several ages, statistical tests over many
seeds, and a time-lapse screenshot series.

## Final QA: `tomato-season`

Browser controls for the day (or thermal time), the seed, temperature, PAR
and CO₂ presets, showing identifiers, the growth speed, and pruning and
harvesting. Watch a row grow from young plants to fruiting ones; check the
same seed repeats exactly and different seeds give plausible, non-clone
variation; check warm, bright conditions and cool, dim ones visibly diverge;
check fruit ripeness matches the state inspected; and check no impossible
topology appears.

## Acceptance criteria

- [ ] Plants are our own implementation.
- [ ] Development is longitudinal and stochastic.
- [ ] Every visible organ has a persistent simulation identity where
  appropriate.
- [ ] Biological state drives geometry and appearance.
- [ ] Environmental coupling exists through an explicit interface.
