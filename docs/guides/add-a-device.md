# Add a device

A device is a kind of climate equipment that a layout places and the climate
run drives: a fan, a heater and a dehumidifier today. Every level, command and
schedule refers to a piece of equipment by its `actuator_id`, not by its kind,
so a new kind does not touch the API, the commands or the live stream. What
it does to the air, how the scene draws it and how the viewer shows it are
the parts to write. The dehumidifier was added in this order (commits
`23a0637`, `8624e23`, `7ee11b4`, `b5b70d4` and `9052f49`).

## Steps

1. **Its kind.** Add a member to `ActuatorKind` in
   `greenhouse_sim/greenhouse_sim/domain/equipment.py`.
2. **Its model.** In `greenhouse_sim/greenhouse_sim/world/equipment.py`, add
   a class:
   - subclass `_Unit` for a box standing on the floor, or `_Equipment` for
     a unit that hangs, as `Fan` does;
   - give it a `kind: Literal[...]`, its rated values and `rated()`;
   - add it to `type Equipment`.

   A unit inherits where it is placed (`anchor`) and how a move or a copy
   places it further (`displaced`) from `_Unit`; a device placed otherwise
   gives its own.
3. **What it does to the air:** its `capabilities()`, made of those in
   `greenhouse_sim/greenhouse_sim/world/capabilities.py` (P14.5): it moves
   air (`MovesAir`, a jet from its outlet), heats (`Heats`, blown from an
   outlet or given around its body), dries (`Dries`), and the heat it gives
   off as it works (`WasteHeat`). Nothing else reads its kind: the
   climate's source terms add its capabilities up
   (`greenhouse_sim/greenhouse_sim/climate/sources.py`), the heating,
   dehumidifying and circulation loops run a device that heats, dries or
   moves air, the house's heating and the heat log are what heats, and the
   builder's findings ask the same. A device that does what no capability
   says (adds CO₂, say) needs a capability of its own, its source terms in
   `climate/sources.py`, and, for a quantity the air does not carry yet, a
   new `SourceTerms` field, kept in `none` and `__add__`, and used by
   `climate/transport.py` and `climate/house.py`.
4. **Place one.** Add it to a layout, such as
   `greenhouse_sim/greenhouse_sim/scenarios/layouts/climate_box/default.json`,
   and update the `layout` note in that scenario's manifest
   (`greenhouse_sim/greenhouse_sim/scenarios/manifests/climate_box.json`).
   Its identifier holds only letters, digits, `_`, `.` and `-`, because the
   API's parameters carry it.
5. **The scene and the viewer** need nothing for a device made of the
   capabilities there are (P14.5). The scene draws every device as one kind
   of entity, `EQUIPMENT`, by its shape, grey while off and in the colour
   of what it is for while it runs, with its kind (`device_kind`), what it
   is for (`does`) and each capability's rating under the capability's
   name (`heats_w`, `moves_air_m3_s`, `dries_kg_h`, `gives_off_heat_w`)
   among its properties (`greenhouse_sim/greenhouse_sim/scene/snapshot.py`).
   The viewer draws it by its shape, puts it in the category of what it
   does, names it by its kind, lists it in the Equipment panel by its
   rating and moves it, whatever its kind. A new capability is added to
   the scene's `EQUIPMENT_COLORS` and, in `greenhouse_sim/web/src/`, to
   `debug/categories.ts` (`EQUIPMENT_CATEGORIES`, `DOES`, its colour and
   label) and `EquipmentControls.tsx` (its rating, in `RATINGS`); a change
   to the scene's types raises `SCHEMA_VERSION`, with a comment that says
   what changed, and `scene/schemaVersion.ts`'s `SUPPORTED_SCHEMA_VERSION`
   with it.
6. **Say so** in the pull request's `## Changelog` section and in
   `greenhouse_sim/web/README.md`.

## Generated files

In this order:

```bash
uv run python greenhouse_sim/tests/test_published_schemas.py --update   # layout.schema.json
uv run python greenhouse_sim/tests/test_scene_schema.py --update        # snapshot schema, example scenes
cd greenhouse_sim/web && npm run generate                               # the viewer's scene types
```

## Tests

```bash
uv run pytest greenhouse_sim/tests/test_equipment.py greenhouse_sim/tests/test_climate_contract.py \
  greenhouse_sim/tests/test_climate_transport.py greenhouse_sim/tests/test_whole_house.py \
  greenhouse_sim/tests/test_equipment_scene.py greenhouse_sim/tests/test_moves.py \
  greenhouse_sim/tests/test_run_identity.py
uv run check --fast
uv run viewer-checks
uv run browser-tests e2e/equipment.spec.ts e2e/climate-actuators.spec.ts e2e/moving.spec.ts
```

Write its own tests beside the others: what it gives the air at each level
in `greenhouse_sim/tests/test_climate_contract.py`, its entity in
`greenhouse_sim/tests/test_equipment_scene.py`, and its panel in
`greenhouse_sim/web/src/EquipmentControls.test.tsx`.

## What else moves

- **Entity counts:** the example scene is the climate box's. A device placed
  there changes the "128 entities" that `e2e/bounds.spec.ts`,
  `e2e/selection.spec.ts`, `e2e/equipment.spec.ts` and others check.
- **Screenshots** change where the device is in view. CI draws their
  baselines, never a local machine.
- **The run's identity** is a digest of the scenario's configuration, so a
  layout with the device is another run, with another id. The CHANGELOG
  entry says so.
- **The protocol** (`greenhouse_protocol`) has no equipment kinds. Only a
  record of a new type touches it, and it is a published contract: see
  [add a sensor kind](add-a-sensor-kind.md).
