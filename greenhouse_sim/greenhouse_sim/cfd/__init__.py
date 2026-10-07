"""Computational fluid dynamics: the greenhouse's air, by an external solver.

The simulator owns the geometry it hands a solver (`geometry`): which
surfaces bound the air, which openings let it through, and which fixtures
stand in its way. It writes them as a case for OpenFOAM (`openfoam`), and
runs OpenFOAM out of process (`runner`), natively or in a container, so that
nothing else in the simulator ever needs it.
"""
