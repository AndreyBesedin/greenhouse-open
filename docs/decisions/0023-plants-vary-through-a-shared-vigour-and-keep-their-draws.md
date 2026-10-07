# 0023: Plants vary through a shared vigour, and keep what they drew

**Status:** Accepted
**Date:** 2026-10-06

## Context

P03.4 makes the plants of one crop differ. Real plants vary together: a
vigorous plant tends to develop faster and grow longer leaves, longer
internodes and a thicker stem. Independent draws for each trait would give
implausible plants, such as a slow plant with oversized leaves, as often as
plausible ones. The variation must replay exactly from a seed (decision
0022), stay within ranges a test can state, and leave the drawn plant
explainable: why this plant is taller than its neighbour.

## Decision

- Each plant draws a latent vigour, a standard normal held within a set
  number of standard deviations. Each trait's factor is 1 plus its
  coefficient of variation times a draw that loads on the vigour as the
  trait's correlation with it says, and on the trait's own draw for the
  rest. Every draw is held within the same limit, so every factor stays
  within a range the configuration states (`VariationParams.factor_range`),
  and a configuration that could vary a trait to nothing is refused.
- What a plant drew is part of its state: its traits (`PlantTraits`) and the
  seed it draws from. Development and geometry read them from the plant, so
  a plant's state, its crop's parameters and its form are all its drawn
  geometry depends on. An organ's own variation, its final size, is drawn
  from the organ's generator when it appears and recorded in the organ, like
  any other state.
- The crop's parameters stay the crop's: `DevelopmentParams` and `PlantForm`
  describe a typical plant, and a plant's traits are factors on them.

## Consequences

- A row of plants varies plausibly, and the reason for any difference can be
  read off the plants' traits.
- A plant's state replays its development and geometry without knowing how
  its traits were drawn, so traits can later be set by hand, fitted to
  measurements, or drawn differently, without changing development.
- The traits are a fixed list. A new varying trait means a new factor in
  `PlantTraits` and a new spread in `VariationParams`.
