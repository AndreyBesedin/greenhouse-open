"""The organ-level tomato model: a plant as the organs it is made of.

A plant grows one main stem (its axis) of phytomers: each a node with the
internode below it and a leaf, and some with a truss of flowers, whose set
flowers become fruits. Every organ has an identity derived from where it
sits in the plant (`topology`), so it is the same organ from one day to the
next and from one run to the next, and its random draws follow a seed
hierarchy of its own (`seeds`). Its geometry is derived from its state
(`geometry`): the viewer draws what the organs say.

It is our own model, inspired by functional-structural plant modelling but
depending on none of its frameworks (P03).
"""
