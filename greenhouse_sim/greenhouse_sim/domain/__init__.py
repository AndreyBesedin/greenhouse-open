"""The words the simulator describes its world in, shared by every part of it.

The kinds, categories and stages that more than one package of the simulator
uses live here, split by what they describe, so that no package has to reach
into another's model for its vocabulary:

    envelope   the envelope's surfaces, members and openings
    layout     fixtures, their materials and obstructions, and zones
    crop       the simple crop model's fruit and truss stages
    organs     a plant's organs, their stages and their allowed changes

The domain depends on nothing else in the simulator. A contract's own
vocabulary stays with its contract: the scene's entity kinds with the scene
(`greenhouse_sim.scene.snapshot`), a live run's commands with its service.
"""
