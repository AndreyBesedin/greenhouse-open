# 0005: Keep a model's own state apart from the world

**Status:** Accepted
**Date:** 2026-10-03

## Context

The hidden world mixed two kinds of value. Some describe what the world is: a
plant's stem length, a fruit's diameter, mass and ripeness, the water in the
root zone. Others exist only because of how the simple tomato model generates
the world: a plant's growth multiplier and water stress, and each fruit's
drawn target diameter, growth-rate multiplier and ripening day. Sensors,
actions and ground truth should depend only on the first kind. Richer models
(P03 for tomatoes, P04 for the environment) will keep different values of the
second kind, and adding them to the world's entities would grow those types
with every model.

The world is also what a run is saved as. Downstream applications persist it
as JSON and load it back, so whatever a model keeps must survive that round
trip with its types intact.

Options considered:

- **A separate run-state object** holding the world and each model's state.
  It is the cleanest split, but every caller of the engine and every
  checkpoint store would have to change. It is worth revisiting when P-1.5
  gives backends their contracts.
- **An untyped mapping on each entity** (`dict[str, float]`). It survives
  JSON, but loses type checking and spreads string keys through the model.
- **A world type that is generic over model state.** It keeps typing, but
  every annotation of the world would need a type parameter.
- **A typed, model-owned section of the world**, chosen here.

## Decision

- World entities (`GreenhouseWorld`, `PlantWorld`, `Truss`, `Fruit`,
  `GreenhouseEnvironment`) hold only what the world is.
- A model's own values live in a state type the model defines, keyed by
  entity identifier. For the simple tomato model that is `SimpleTomatoState`,
  carried as `GreenhouseWorld.plant_model`, and tagged with the model's name
  so a saved world records which model produced it.
- Only the model itself and the module that composes the models read that
  section. A test enforces this, as it does for ground truth.
- An action changes the world, not a model's state. Watering adds water to
  the root zone, and the plant model responds to the new value on the next
  day.

## Consequences

- Sensors, actions, ground truth and evaluation can no longer depend on one
  model's internals.
- `world/state.py` names the type of the plant model's section. A second
  plant model turns that field into a union of state types tagged by model,
  rather than adding fields to the entities.
- The serialized world changed: worlds saved before this decision do not load
  (`plant_model` is missing). That is acceptable while the packages are
  unpublished, and recorded as a breaking change.
