# P03 clean-up

**Status:** collecting. Part of [P03](p03-tomato-development.md).

The reviews of P03's pull requests find things best done once P03's steps
are merged, in one pass, before the next project builds on the plant model.
Each review adds what it finds here, under its pull request. The clean-up
itself is one pull request at the end of P03, which ticks each item off or
says why it was dropped.

## To do

### From #47, P03.1: plant topology and organ state

- [ ] **Shared domain descriptors.**
  - **What:** the organs' kinds, the stages of leaves, flowers and fruits,
    and the changes allowed between them are domain knowledge. The scene and
    the services use them as well as biology.
  - **Where to:** move them, and the other descriptors shared across
    packages, out of `biology/tomato/organ/topology.py` into a
    `greenhouse_sim/domain/` package.
  - **How:** split the package by concept, so it doesn't become one module
    that everything imports and nobody owns.
- [ ] **A generic plant, with tomato as one kind of it.**
  - **What:** put the structure fruiting crops share in `biology`, with the
    tomato as one implementation.
  - **Generic:** an organ's appearance in thermal time, the axis, the
    phytomer, the internode and the leaf; the stages of leaves, flowers and
    fruits and their allowed changes; the actions and the history.
  - **The tomato's own:** the truss as its inflorescence, its compound leaf's
    form, its maturity classes, and all of its parameters.
  - **Caution:** only move what is clearly generic. With one crop to go on,
    generic base classes guess. P09, which connects the organ model to the
    engine, is a second user to check the line against.

## Left for the audit after P07

These came up in P03's reviews, but belong to the wider audit planned after
P07:

- **CRC32 in `core.rng.stable_int`:** it hashes identifiers into seeds. Two
  identifiers can collide, and then share a random stream. A 64-bit hash
  would make that vanishingly rare, but changing it changes every
  scenario's draws and the baselines tuned to them.
