"""Environment fields: the greenhouse's air, cell by cell.

An environment field (`field`) is the exchange format between whatever
computes the air's state, a prescribed pattern, a zonal model or a CFD solver,
and whatever uses it: the viewer today, plants and sensors later. Its grid
covers a box with regular cells, and each of its channels holds one quantity
of the air at every cell's centre.
"""
