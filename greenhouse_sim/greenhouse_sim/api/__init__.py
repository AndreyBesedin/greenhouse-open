"""A thin local API that lets the browser viewer reach the simulator.

It is an adapter around the simulator, never part of it: nothing else in
the package imports it, and the simulator runs without it. It serves only
what a viewer needs to look at a simulation, and never ground truth.

It is the interface to the simulator's services (`greenhouse_sim.services`):
its routes read requests, call services, and turn their results and errors
into responses; the logic is the services'.
"""
