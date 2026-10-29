"""Reduced-State TOMGRO, a crop model grown by area (decision 0060).

Jones, Kenig and Vallejos (1999, doi:10.13031/2013.13203) reduce TOMGRO to
five states, each per m² of greenhouse floor: the main stem's nodes, the
leaf area index, and the dry weights above ground, of the fruit and of the
mature fruit. The variant is Oliveira et al.'s (release v0.4.0,
doi:10.5281/zenodo.13294322): the paper's forms, with those of Jones's
spreadsheet where they differ, as its inventory lists them
(`docs/research/reduced-tomgro-inventory.md`).

Its equations are those of its reproduction
(`research/reproductions/reduced_tomgro/model.py`, milestone A), which
agrees with the reference within 1e-9 of every state; the package's are
held to the same reference output (`greenhouse_sim/tests/test_tomgro.py`).
Its parameters are the parameter set `gnvman` and the inputs `gnv_n01`
(`parameters`), each with its unit and source.

It is a prediction until it is validated on measured data (decision 0060,
milestone C).
"""
