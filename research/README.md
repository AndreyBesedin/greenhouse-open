# Research

Work the [research priorities](../docs/roadmap/research-validation-priorities.md)
call for that is not part of the packages: nothing in `greenhouse_sim`,
`greenhouse_protocol` or `greenhouse_adapters` imports it.

- [`reproductions/`](reproductions/): published models reproduced on
  their own, each compared with a pinned reference implementation on the
  same drivers (decision 0060, milestone A). `tests/test_reproductions.py`
  holds each to its reference.
- [`validation/`](validation/): what measured data hold for a model to
  be held to (item 5), counted file by file.
  [`agc4/`](validation/agc4/README.md) profiles the two AGC4 archives,
  builds the hourly drivers decision 0076 runs the tomato models on, runs
  the models on them, and calibrates each on the 2023 pre-trial.
- [`integrations/`](integrations/): what the run's way of driving a
  reproduced model changes of it (decision 0062, milestone B), measured
  against the reproduction's forcing and against a reference's
  greenhouse. [`driver_profiles/`](integrations/driver_profiles/README.md)
  measures the first driver profile for both tomato models.

The memos that plan this work are in [`docs/research/`](../docs/research/README.md).
