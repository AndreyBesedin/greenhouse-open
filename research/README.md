# Research

Work the [research priorities](../docs/roadmap/research-validation-priorities.md)
call for that is not part of the packages: nothing in `greenhouse_sim`,
`greenhouse_protocol` or `greenhouse_adapters` imports it.

- [`reproductions/`](reproductions/): published models reproduced on
  their own, each compared with a pinned reference implementation on the
  same drivers (decision 0060, milestone A). `tests/test_reproductions.py`
  holds each to its reference.

The memos that plan this work are in [`docs/research/`](../docs/research/README.md).
