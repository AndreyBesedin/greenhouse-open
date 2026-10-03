"""A thin local API that lets the browser viewer reach the simulator.

It is an adapter around the simulator, never part of it: nothing else in
the package imports it, and the simulator runs without it. It serves only
what a viewer needs to look at a simulation, and never ground truth.
"""
