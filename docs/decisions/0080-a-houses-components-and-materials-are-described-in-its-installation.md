# 0080: A house's components and materials are described in its installation

**Status:** Proposed, with [P24](../roadmap/p24-house-components-and-a-multi-node-climate.md)'s plan
**Date:** 2026-11-16

## Context

- **An installation is the house part of a scenario** (decision 0050):
  its envelope, its layout and each row's crop, edited in the builder and
  carried as a file of its own. The models' settings are the scenario's,
  and stay out of it.
- **What a house is made of is a model's setting today.** The glazing's
  U and the infiltration are the house air model's parameters (`climate`
  section); the glass's transmittance is the sunlight model's constant
  (0.85 for single glass). A fixture names a material (steel, aluminium,
  plastic, concrete, substrate) for what it obstructs, not for its heat
  or its light. A wall always faces the outside. There are no screens,
  floors or pipe networks to describe.
- **A model that needs more has nowhere to read it.** A multi-node
  climate (decision 0078) needs each surface's material, each wall's
  boundary, the floor's layers, the screens and the pipes. Put in its own
  parameters, they would describe the house a second time, apart from
  the envelope and the layout, and a grower's house could not be told
  apart from a model's choice.
- **Modellers describe a house by its components.** TiGwerLib and
  GreenLight each give a house its cover, screens, floor, pipes and
  neighbouring spaces as parameters. A house described once, in those
  terms, can be written to their parameters and read back, so that a
  comparison gives both sides one setup.

## Decision

**The installation describes what a house is made of and what it has.**
Its envelope and layout gain:

- **the cover's materials:** each surface's, the roof's and each wall's;
- **each wall's boundary:** the outside, the default; a neighbouring
  space at a temperature, constant or recorded (a corridor, a headhouse,
  another house); or nothing, across which no heat passes;
- **the floor:** its surface, its layers to a depth, and the deep soil's
  temperature;
- **screens:** each thermal, shading or blackout screen, its material, its
  height and extent, and its drive, a device with a level from 0 (open) to
  1 (closed), which commands and a loop run;
- **pipe networks:** a kind of equipment (decision 0055), with its pipes'
  geometry and emissivity, and how its heat leaves, by convection and by
  radiation.

**A material is named, or given by its properties.** A catalogue of named
materials (single glass, diffuse glass, double glass, twin-wall
polycarbonate, polyethylene film, concrete, soil, screen cloths) gives
each property its value, unit and source. A material given by its
properties is checked against each property's range. A named material's
values never change once published; a correction is a new name.

**A model's parameters keep only how it computes:** its laws, its
tolerances, its choices. What the house is stays in the installation, and
a model reads it from there.

**A described cover gives every model its glass.** A cover's material
gives `grid` and `whole_house` their U and their transmittance, and the
sunlight its transmittance. A manifest that gives both a cover's
material and the house air model's `glazing_u_w_m2k` is refused, naming
both; a manifest that gives no material runs on the parameter, as today.

**A neighbouring space's recorded temperature is a file of its own,**
digested into the run's identity as a recorded weather is.

**A model that cannot model a described component refuses the house,**
naming the component, as a run refuses rows of crops it cannot grow. It
never runs as if the component were not there.

**A component left undescribed writes nothing,** so that a manifest that
describes none is written as it was, and no packaged run id, checkpoint
or replay digest moves.

**One schema, reached in the builder.** The components are part of the
published `installation.schema.json` and the manifests' format, migrated
as decision 0050 has it, and every field is reached in the builder from
the schema.

**A house can be written to a reference's parameters, and read back.** A
mapping names each field's counterpart in TiGwerLib's and in GreenLight's
parameters, its conversion of units, and the fields with none on either
side, which it reports rather than drops. It lives under `research/`,
beside the references it maps to, until a package needs it.

## Consequences

- **The manifests' format changes,** by fields left out when undescribed;
  the viewer's contracts are generated again.
- **The glass's U and transmittance gain a second source:** a cover's
  described material, beside the house air model's `glazing_u_w_m2k` and
  the sunlight's constant. A manifest gives one or the other, never both.
- **Today's models refuse a house they cannot model,** such as one with a
  screen under `whole_house`, where today they could not be told of one.
- **The builder grows palettes** for screens, floors and pipe networks,
  and a material picker.
- **Worth revisiting:**
  - if a component's description depends on the model that reads it,
    which would put the model's choice back into the house;
  - if materials need versions of their own, as crop parameter sets have
    (decision 0077), rather than new names.

## Open questions

None: the three it was proposed with are answered above (a described
cover gives every model its glass, and a manifest giving both is refused;
a neighbouring space's record is a file of its own; and this record
stands apart from decision 0078, since the sunlight and the grid read a
material too).
