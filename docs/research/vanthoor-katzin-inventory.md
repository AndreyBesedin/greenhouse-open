# Vanthoor's tomato model as GreenLight implements it: an inventory

What a reproduction of Vanthoor's tomato yield model, as Katzin (2021)
simplified it, has to match, read from the reference implementation:
GreenLight 2.0.7, commit `d6282a1` (tag `v2.0.7`), its three files

- `greenlight/models/katzin_2021/definition/vanthoor_2011/crop_vanthoor_2011_chapter_9_simplified.json`
  (the crop),
- `.../vanthoor_2011/extension_crop_vanthoor_2011_for_standalone.json`
  (the standalone extension, which works out the PAR absorbed), and
- `.../vanthoor_2011/main_vanthoor_crop.json` (the composition of a
  standalone run).

The crop's files are unchanged since GreenLight 2.0.2. "Table" and "Eq"
are those of Vanthoor's thesis, *A model-based greenhouse design method*
(Wageningen University, 2011, [edepot.wur.nl/170301](https://edepot.wur.nl/170301)),
unless another source is named; Katzin (2021) is
[doi:10.18174/544434](https://doi.org/10.18174/544434). Units are as the
files write them. Checked on 2026-10-29, by the
[tomato model memo](tomato-model-feasibility.md).

## The version to run

- **PyPI:** `greenlight` 2.0.7, uploaded 2026-10-27, the latest release;
  `GreenLight` is the same project, its name normalised. Pinned by its
  files' hashes: wheel
  `67b24ac7138cea3cc91cbba801ba1a33114ff006921f28add4313817870eaf9e`, sdist
  `7920704897eb7534adf2ecab4dafd796f17a11a5bb51ea6d44512d038b3878e4`.
  Release 0.1 of the same project, from 2010, is unrelated software: a
  loose version range could install it.
- **Its dependencies** (numpy, scipy, pandas, numexpr) carry no bounds in
  2.0.7, so the reproduction locks them itself.
- **The source cited** is the commit; its crop, solver and conversion files
  are byte for byte the wheel's. The repository's test data are Git LFS
  pointers, so the wheel, not a checkout, is what runs.

## States

Six ODE states. The leaf area index is derived, not a state.

| State | Unit | What | Derivative as written | Initial value | Its source |
| --- | --- | --- | --- | --- | --- |
| `cBuf` | mg{CH2O} m⁻² | carbohydrates in the buffer | `mcAirBuf - mcBufFruit - mcBufLeaf - mcBufStem - mcBufAir` (Eq 9.1) | 20e3 | none named; the file names GreenLight 1's `setGlInit.m`, which sets 0 |
| `cFruit` | mg{CH2O} m⁻² | in the fruit | `mcBufFruit - mcFruitAir - mcFruitHar` (Eq 9.2; Katzin 2021 Eq 7.43) | 312 | `setGlInit.m`, 0.05 × 6240 |
| `cLeaf` | mg{CH2O} m⁻² | in the leaves | `mcBufLeaf - mcLeafAir - mcLeafHar` (Eq 9.4) | 4368 | `setGlInit.m`, 0.7 × 6240 |
| `cStem` | mg{CH2O} m⁻² | in the stems | `mcBufStem - mcStemAir` (Eq 9.6) | 1560 | `setGlInit.m`, 0.25 × 6240 |
| `tCanSum` | °C day | the crop's temperature sum, an integral | `tCan / 86400` (Eq 9.8, its unit changed) | 0 | `setGlInit.m` |
| `tCan24` | °C | the canopy's temperature over the last day, a first-order filter with a time constant of 86,400 s | `(tCan - tCan24) / 86400` (Eq 9.9, A.2) | 20.5 | none named |

`lai = sla * cLeaf` (Eq 9.5).

## Parameters

| Name | Value | Unit | What | Source |
| --- | --- | --- | --- | --- |
| `laiMax` | 3 | m² leaf m⁻² floor | the most leaf area | Table 2.2 (the Netherlands) |
| `alpha` | 0.385 | µmol e⁻ µmol⁻¹ photons | photons to electrons | Table 9.1 |
| `theta` | 0.7 | – | curvature of the electron transport | Table 9.1 |
| `etaCo2AirStom` | 0.67 | – | the air's CO₂ to the stomata's | Table 9.1 |
| `cGamma` | 1.7 | µmol mol⁻¹ K⁻¹ | temperature's effect on Γ | Table 9.1 |
| `cFruitM`, `cLeafM`, `cStemM` | 1.16e-7, 3.47e-7, 1.47e-7 | mg mg⁻¹ s⁻¹ | maintenance respiration | Table 9.1 |
| `cFruitG`, `cLeafG`, `cStemG` | 0.27, 0.28, 0.3 | – | growth respiration | Table 9.1 |
| `cRgr` | 2.85e6 | written s⁻¹ | regression coefficient of maintenance respiration | Table 9.1; `cRgr * rgr` is dimensionless, so the unit should read s |
| `cBufMax`, `cBufMin` | 20e3, 1e3 | mg m⁻² | the buffer's most and least | Table 9.1 |
| `eJ`, `H`, `S` | 37e3, 22e4, 710 | J mol⁻¹, J mol⁻¹, J mol⁻¹ K⁻¹ | activation, deactivation, entropy | Table 9.1 |
| `j25LeafMax` | 210 | µmol e⁻ m⁻² leaf s⁻¹ | the most electron transport at 25 °C | Table 9.1 |
| `mCh2o` | 30e-3 | mg µmol⁻¹ | molar mass of CH₂O | Table 9.1 |
| `rgFruit`, `rgLeaf`, `rgStem` | 0.328, 0.095, 0.074 | mg m⁻² s⁻¹ | potential growth | Table 9.1 |
| `sla` | 2.66e-5 | m² leaf mg⁻¹ | specific leaf area | Table 9.1 |
| `t25k` | 298.15 | K | reference temperature | Table 9.1 |
| `tEndSum` | 1035 | °C day | temperature sum to a fully generative crop | Table 9.1, its unit changed |
| `q10m` | 2 | – | Q10 of maintenance respiration | Table 9.1 |
| `tCanMin`, `tCanMax` | 10, 34 | °C | the instantaneous temperature's inhibition | Table 9.2 |
| `tCan24Min`, `tCan24Max` | 15, 24.5 | °C | the last day's temperature's inhibition | Table 9.2 |
| `rgr` | 3e-6 | s⁻¹ | relative growth rate, a constant | GreenLight 1's `setGlParams.m`, "assumed" |
| `mCo2` | 44e-3 | mg µmol⁻¹ | molar mass of CO₂ | `setGlParams.m` |
| `R` | 8314 | J kmol⁻¹ K⁻¹ | gas constant | Table 8.1 (Table 9.1 gives 8.314 J mol⁻¹ K⁻¹) |
| `cLeafMax` | `laiMax / sla`, about 1.128e5 | mg m⁻² | the most leaf | Eq 9.46 |
| `cFruitMax` | 300e3 | mg m⁻² | the most fruit unharvested | Katzin (2021), p. 246 |
| `k1Par`, `k2Par` | 0.7, 0.7 | – | the canopy's extinction of PAR, from above and from the floor | Table 8.1 (extension) |
| `rhoCanPar` | 0.07 | – | the canopy's reflection of PAR | Table 8.1 (extension) |
| `rhoFlrPar` | 0.65 | – | the floor's reflection of PAR | Table 8.2, the Netherlands (extension) |

Constants written into definitions: 86400 (the day, in `tCanSum` and
`tCan24`); 273.15 and a 1e-3 scaling of `R` (`jPot`); 4 and 2 (`p`); 20
(`gamma`); 0.047 and 0.06 (`gTCan24`, Eq 9.28); 5e-4 (`hAirBuf`), -5e-3
(`hBufOrg`); -0.869 and 0.5793 (`hTCan`); -1.1587 and 1.3904 (`hTCan24`);
1e-4 (`hTCanSum`); log(100) (`smoothHar`); and the harvests' smoothing
and most rates, 1e4 and 1e5 for leaves, 1e4 and 5e4 for fruit.

## Derived variables

| Name | Definition as written | Source |
| --- | --- | --- |
| `mcAirBuf` | `mCh2o * hAirBuf * (p - r)` | Eq 9.10 |
| `p` | `j * (co2Stom - gamma) / (4 * (co2Stom + 2 * gamma))` | Eq 9.12 |
| `r` | `p * gamma / co2Stom` | Eq 9.13 |
| `j` | the non-rectangular hyperbola of `jPot` and `alpha * parCan`, curvature `theta` | Eq 9.14 |
| `jPot` | the Arrhenius form of `j25CanMax` in the canopy's temperature | Eq 9.15 |
| `j25CanMax` | `lai * j25LeafMax` | Eq 9.16 |
| `co2Stom` | `etaCo2AirStom * co2InPpm` | Eq 9.21 |
| `gamma` | `(j25LeafMax / j25CanMax) * cGamma * tCan + 20 * cGamma * (1 - j25LeafMax / j25CanMax)`; with `j25LeafMax / j25CanMax = 1 / lai`, singular at no leaf area | Eq 9.23 |
| `mcBufFruit` | `hBufOrg * hTCan * hTCan24 * hTCanSum * gTCan24 * rgFruit` | Eq 9.24 |
| `mcBufLeaf`, `mcBufStem` | `hBufOrg * hTCan24 * gTCan24 * rgLeaf` (`rgStem`) | Eq 9.25 |
| `gTCan24` | `0.047 * tCan24 + 0.06` | Eq 9.28 |
| `mcBufAir` | growth respiration: `cLeafG * mcBufLeaf + cStemG * mcBufStem + cFruitG * mcBufFruit` | Eq 9.43–9.44 |
| `mcLeafAir`, `mcStemAir`, `mcFruitAir` | maintenance respiration: `(1 - exp(-cRgr * rgr)) * q10m ** (0.1 * (tCan24 - 25)) * c{Org} * c{Org}M` | Eq 9.45 |
| `hAirBuf`, `hBufOrg` | the buffer's smooth switches | Eq 9.11, 9.26, B.1 |
| `hTCan`, `hTCan24`, `hTCanSum` | temperature's smooth inhibitions | B.2, B.3, Eq 9.27, B.6 |
| `smoothHar(x, cutOff, smooth, maxRate)` | `maxRate / (1 + exp(-(x - cutOff) * 2 * log(100) / smooth))` | Katzin (2021) Eq 7.45 |
| `mcLeafHar` | `smoothHar(cLeaf, cLeafMax, 1e4, 1e5)`: leaf pruning | Eq 9.47, B.5; 1e5 in place of the published 5e4, following Katzin (2021)'s dataset |
| `mcFruitHar` | `smoothHar(cFruit, cFruitMax, 1e4, 5e4)`: the fruit harvested | Katzin (2021) Eq 7.45 |
| `parGhCan` | `parGh * (1 - rhoCanPar) * (1 - exp(-k1Par * lai))` | Eq 9.18 (extension) |
| `parFlrCan` | `rhoFlrPar * parGh * (1 - rhoCanPar) * exp(-k1Par * lai) * (1 - exp(-k2Par * lai))` | cited as "Eq 9.1", read as Eq 9.19 (extension) |
| `parCan` | `parGhCan + parFlrCan`: the PAR the canopy absorbs, which photosynthesis uses | Eq 9.17 (extension) |

**Incident and absorbed PAR:** `parGh`, the PAR above the canopy, is an
input. `parCan`, the PAR the canopy absorbs, is worked out from it by the
standalone extension; in the crop's own file it is an input, defined by
the greenhouse model.

## Inputs of a standalone run

`tCan` (°C, the canopy's temperature), `parGh` (µmol photons m⁻² s⁻¹, the
PAR above the canopy) and `co2InPpm` (ppm), each a column of a series
whose `Time` is in seconds, interpolated linearly between rows, and held
at its first or last row outside them.

The example's series (`main_vanthoor_crop.json`, 120 days from 15 May) is
not in the repository: it is made from an EnergyPlus weather file by
`greenlight.convert_energy_plus(..., output_format="vanthoor_crop")`,
hourly, with `tCan` the outdoor dry-bulb temperature, `parGh` 2.3 times
the outdoor global horizontal radiation, and `co2InPpm` a constant, 410
ppm by default; GreenLight calls it "a quite artificial dataset", the crop
taken to be outdoors. Its time zone is not stated.

## Outputs

Every state, input and derived variable, interpolated linearly onto an
hourly grid that leaves out the last moment. The harvests are rates
(`mcFruitHar`, `mcLeafHar`, mg{CH2O} m⁻² s⁻¹), not states: the harvested
fruit is their integral over time. Every crop quantity is a mass of
carbohydrate (CH₂O); the files give no factor to dry or fresh matter.

## Solver

scipy's `solve_ivp`, method BDF, `max_step` 3600 s, `atol` 1e-3 (one
scalar, in each state's own unit), `rtol` 1e-6, output every 3600 s. It
sets NaNs to 0 and clips values past ±1e38 without saying so.

## Departures the files note

- "Some simplifications as in Katzin (2020) and Katzin (2021)", listed
  there, not in the files.
- `parCan` moved out of the crop, an input of it.
- Leaf pruning's most rate 1e5 rather than the published 5e4.
- The fruit harvested by Katzin (2021)'s smooth harvest, with `cFruitMax`
  300e3; which of the thesis's fruit equations it replaces, the files do
  not say.
- `rgr` a constant, "assumed".
- `R` taken as 8314 J kmol⁻¹ K⁻¹ with 1e-3 factors, where Table 9.1 has
  8.314 J mol⁻¹ K⁻¹.
- The units of `tCanSum` and `tEndSum` changed from the thesis's.
- `cBuf`'s initial value, 20e3, not GreenLight 1's 0.

Oliveira et al.'s Vanthoor implementation (see the
[TOMGRO inventory](reduced-tomgro-inventory.md)) is another variant, with
fruit development stages, and is not checked against this one.
