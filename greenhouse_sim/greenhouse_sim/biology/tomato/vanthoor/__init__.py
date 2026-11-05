"""Vanthoor's tomato yield model as Katzin simplified it, a crop model grown
by area (decision 0060).

Vanthoor (2011, chapter 9, edepot.wur.nl/170301) with the simplifications of
Katzin (2021, doi:10.18174/544434), as GreenLight 2.0.7 writes them
(`docs/research/vanthoor-katzin-inventory.md`): six states over a course of
the day, a carbohydrate buffer filled by photosynthesis and drawn on by the
fruit, the leaves and the stems, with the temperature sum and the canopy's
temperature over the last day. Its quantities are carbohydrate equivalents
per m² of greenhouse floor, never dry matter.

Its equations are those of its reproduction
(`research/reproductions/vanthoor_katzin/model.py`, milestone A); the
package's are held to the same reference output
(`greenhouse_sim/tests/test_vanthoor.py`). Its parameters are GreenLight's,
each with its unit and source in the reproduction's manifest.

- **How it integrates** is its own (decision 0064): `growth.live_hour`, four
  stages at a fixed step, with no memory from one hour to the next, where
  the reference takes the steps its solver chooses.
- **Where its equations misbehave:** the CO₂ compensation point (Eq 9.23)
  is divided by the leaf area index, as written. At the leaf area it is
  planted with, 0.12, the point is negative below about 18 °C, and under
  400 µmol m⁻² s⁻¹ and 420 ppm its assimilation goes from 1.9 µmol m⁻² s⁻¹
  at 20 °C to 22 at 10 °C, through a pole near 8 °C and negative below
  that. The pole has gone by a leaf area index of 0.3. The reference's season
  grows past 0.3 in about a day, never that cold; the equation is not
  changed here.

It is a prediction until it is validated on measured data (decision 0060,
milestone C).
"""
