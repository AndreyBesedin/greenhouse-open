# 0025: Shared vocabulary lives in a domain package, and a crop builds on a generic plant

**Status:** Accepted
**Date:** 2026-10-07

## Context

The review of P03's first pull request found two things that would only grow
harder to change.

- **Shared vocabulary in private places:** kinds, categories and stages were
  defined in whichever model first needed them, and other packages reached
  into that model for them. The scene, for example, read the organs' kinds
  and stages from the tomato's topology, and the envelope's and layout's
  kinds from the world's models.
- **Crop-independent parts filed under the tomato:** much of the
  organ-level tomato model is not the tomato's at all. That covers its
  internodes, leaves, flowers and fruits, the seed hierarchy, the environment
  interface and plant variation, which any fruiting crop would share.

## Decision

- **A domain package.** `greenhouse_sim.domain` holds every kind, category
  and stage that more than one package of the simulator uses. It is split by
  what they describe: `envelope`, `layout`, `crop` (the simple crop
  model's stages) and `organs` (organ kinds, their stages and their allowed
  changes), not gathered in one module. The domain depends on nothing else
  in the simulator.
- **Contracts keep their vocabulary:** the scene's entity kinds stay in
  `greenhouse_sim.scene.snapshot`, and a live run's commands with its service.
- **Enforced by a test:** `tests/test_domain.py` fails if the domain imports
  another package, or if a package imports another package's enum from
  anywhere but the domain.
- **A generic plant.** `greenhouse_sim.biology.plant` holds what fruiting
  crops' organ-level models share: the organs (internode, leaf, flower,
  fruit), a plant's traits, the seed hierarchy, growth curves, the
  environment interface and its responses, and plant variation.
  - **Parameters stay with each crop:** its parameter classes carry no
    crop's values. The tomato's are in
    `greenhouse_sim.biology.tomato.organ.parameters`.
- **What stays the tomato's:** its truss, the phytomer, axis and plant that
  hold it, its identifiers for trusses, flowers and fruits, its structural
  rules, its development, trusses and fruit, its actions and history, and
  its form.

## Consequences

- No package reaches into another's model for a word. A new shared kind has
  one obvious home, and the test keeps it there.
- The world's public path for the simple model's stages
  (`greenhouse_sim.world`) keeps working, re-exporting them from the domain.
- A second crop can reuse the generic plant without importing the tomato.
- Where the line between generic and tomato is uncertain, the code stays
  with the tomato for now:
  - **Actions and history:** they include harvesting a truss, the tomato's
    inflorescence.
  - **Development:** it grows the tomato's phytomers, trusses included.
  - **Fruit growth and ripening:** its values and maturity classes are the
    tomato's.

  P09, which connects the organ model to the engine, is the second user to
  check this line against, and a second crop the next.
