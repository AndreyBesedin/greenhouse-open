"""The simple tomato model: daily rules, kept as the reference model.

One step is one day. Each plant has a water reservoir that empties with use
and builds up stress when low, a stem that grows by a daily amount scaled by
water stress, temperature and a per-plant vigour, and a new truss of three to
six fruits at a fixed interval of plant age. Each fruit grows towards a drawn
target diameter along a saturating curve, and ripens by its age relative to a
drawn ripening day, sooner in warmer conditions.

It is not a calibrated crop model. It has no light, CO2 or organ structure
beyond trusses and fruits, and fruit ripens long before it nears its target
size, so harvested fruit is light: between about 0.2 g and 2 g on average
across the reference scenarios. It stays because it is fast, deterministic
and well characterized: the default for examples and smoke tests, and the
baseline that richer tomato models are compared against.
"""
