# Recorded weather

Weather files any scenario can be run under, by their names
(`&weather=example_day`), in the format `greenhouse_sim.weather.recorded`
reads: a `timestamp` column and one column per outside observation type.

- `example_day.csv` is an example of the format, not a measurement. It is
  generated from the windy autumn day's profile (`weather/presets.py`) on
  1 October 2026 in Amsterdam, every ten minutes, with seeded noise, a
  slowly falling pressure and half an hour of humidity left out, so that
  tests and the viewer have a day with a short gap to replay. A measured
  day can be added beside it in the same format.
