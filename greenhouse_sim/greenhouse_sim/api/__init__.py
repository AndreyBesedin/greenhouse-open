"""A thin local API that lets the browser viewer reach the simulator.

It is an adapter around the simulator, never part of it: nothing else in
the package imports it, and the simulator runs without it. It serves what a
viewer needs to look at a simulation: the simulated world as it is, what
its sensors report, and, for QA mode, what they truly sampled (decision
0036). A policy reads observations only, never this API.

It is the interface to the simulator's services (`greenhouse_sim.services`):
its routes read requests, call services, and turn their results and errors
into responses; the logic is the services'.
"""
