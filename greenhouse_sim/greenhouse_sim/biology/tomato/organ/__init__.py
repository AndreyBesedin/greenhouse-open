"""The organ-level tomato model: a plant as the organs it is made of.

A plant grows one main stem (its axis) of phytomers: each a node with the
internode below it and a leaf, and some with a truss of flowers, whose set
flowers become fruits. It builds on what fruiting crops share
(`greenhouse_sim.biology.plant`): their organs, the seed hierarchy their
draws follow, the environment they live in and how their plants vary. What
is the tomato's own is here: its structure and identities (`topology`), its
development (`development`), trusses (`reproduction`) and fruit (`fruit`),
what a grower does to it (`actions`), its form and geometry (`geometry`),
and its values for the shared parts (`parameters`). Its geometry is derived
from its state: the viewer draws what the organs say.

It is our own model, inspired by functional-structural plant modelling but
depending on none of its frameworks (P03).
"""
