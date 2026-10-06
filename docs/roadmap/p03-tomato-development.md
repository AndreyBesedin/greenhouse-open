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
| P03.2 | `feat(plants): procedural stem, internode and leaf geometry` | Planned |
| P03.3 | `feat(plants): add thermal-time organogenesis` | Planned |
| P03.4 | `feat(plants): add correlated stochastic plant variation` | Planned |
| P03.5 | `feat(plants): add trusses, flowers and fruit set` | Planned |
| P03.6 | `feat(plants): add fruit growth, ripeness and colour` | Planned |
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

### P03.3: Thermal-time organogenesis

Accumulated thermal time, phytomer appearance, internode elongation and leaf
expansion, with configurable developmental rates. Visible result: a time
slider grows one plant from transplant size to a taller vegetative plant.
Tests: a fixed environment and seed give exact organ counts at reference
dates.

### P03.4: Correlated stochastic plant variation

A plant-level latent vigour, and variation in phyllochron, internode length,
leaf scale and orientation, drawn from seeded generators. Visible result: a
row of 20 plants that clearly varies while remaining recognisably the same
crop. Tests: the same seed reproduces geometry, different seeds change
plants, and distributions stay within their configured ranges.

### P03.5: Trusses, flowers and fruit set

Truss initiation rules, flower appearance, stochastic fruit set and
abortion, and stable fruit identity. Visible result: plants develop visible
trusses, flowers and small green fruits over time. Tests: fruit identifiers
persist through growth, and an aborted fruit follows an allowed state
transition.

### P03.6: Fruit growth, ripeness and colour

A fruit size and mass curve, maturity stages, a green to breaker to orange
and red appearance mapping, and a stochastic ripening offset. Visible
result: a time-lapse visibly changes fruit size and colour. Tests: ripeness
never decreases, and the drawn colour is derived from biological state.

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
