"""Airflow models: what moves the greenhouse's air, and how.

Every airflow model (`contract.AirflowModel`) produces an environment field
(`greenhouse_sim.fields`) over whatever grid it is given, so any of them,
from a prescribed pattern to a CFD solver, serves the viewer, and later
plants and sensors, alike. The prescribed patterns (`prescribed`) are the
lightest: known shapes of flow, cheap enough to switch between at once.
"""
