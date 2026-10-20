# Add a sensor kind

A point sensor reads one quantity of the air at its position, or of the
weather if it stands outside, at its cadence and with its imperfections, and
reports it as one of the protocol's observations. A new kind names what it
reads, its unit, the field quantity it samples and the observation type it
reports. The weather station's instruments were added this way (commit
`9e19e21`), with the protocol's observation types they lacked.

## Steps

1. **Its kind:** a member of `SensorKind` in
   `greenhouse_sim/greenhouse_sim/domain/sensors.py`.
2. **Its model:** in `greenhouse_sim/greenhouse_sim/world/sensors.py`, its
   unit in `UNITS`, the kind in the `PointKind` literal, and in
   `WEATHER_KINDS` if it stands outside the house.
3. **What it reads:** in `greenhouse_sim/greenhouse_sim/sensors/air.py`,
   - the quantity it samples, in `QUANTITIES` (a field's quantity, from
     `greenhouse_sim/greenhouse_sim/domain/air.py`) or, outside, in
     `WEATHER_QUANTITIES`;
   - the observation type it reports, in `OBSERVATION_TYPES`;
   - the range it can measure, in `MEASURING_RANGES`;
   - `GOING_ROUND`, if its readings wrap round, as a wind vane's do.
4. **A new observation type**, if none fits, in `ObservationType` in
   `greenhouse_protocol/greenhouse_protocol/enums.py`. The protocol is a
   published contract that consumers read: its change goes in
   `CHANGELOG.md`, and its own tests run.
5. **Place one** in a layout
   (`greenhouse_sim/greenhouse_sim/scenarios/layouts/<scenario>/<name>.json`),
   its identifier made of letters, digits, `_`, `.` and `-`.

The scene's schema does not change: a sensor's kind is a property of its
entity, not an entity kind.

## Generated files

```bash
uv run python greenhouse_sim/tests/test_published_schemas.py --update   # layout.schema.json
```

## Tests

```bash
uv run pytest greenhouse_sim/tests/test_sensors.py greenhouse_sim/tests/test_sensor_observations.py \
  greenhouse_sim/tests/test_weather_station.py greenhouse_sim/tests/test_published_schemas.py
uv run pytest greenhouse_protocol/tests/test_enums.py tests/test_conformance.py
uv run check --fast
uv run browser-tests e2e/sensors.spec.ts
```

A new kind's test samples a field or a weather whose value is known, and
checks the reading, its unit and its observation type, clean and with each
imperfection, as `greenhouse_sim/tests/test_sensors.py` does for the others.
