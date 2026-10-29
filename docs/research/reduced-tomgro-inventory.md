# Reduced-State TOMGRO as Oliveira et al. implement it: an inventory

What a reproduction of Reduced-State TOMGRO has to match, read from the
implementation it is compared with: Oliveira et al.'s
[data-assimilation-tomato-models](https://github.com/mnqoliveira/data-assimilation-tomato-models),
release v0.4.0, commit `b9b2c80`, archived at
[doi:10.5281/zenodo.13294322](https://doi.org/10.5281/zenodo.13294322)
(md5 `43302bcf319dba522f84d80e9b4280a5`). Line numbers are at that commit.
Checked on 2026-10-29, by the [tomato model memo](tomato-model-feasibility.md).

## What it is

- **Not the authors' code.** A Python implementation by M. Oliveira, begun
  in 2019. Its header says its functions and parameters are taken from
  Jones, Kenig and Vallejos (1999,
  [doi:10.13031/2013.13203](https://doi.org/10.13031/2013.13203)) except
  where it says otherwise, and that auxiliary information came from Jones
  et al. (1991,
  [doi:10.13031/2013.31715](https://doi.org/10.13031/2013.31715)) and a
  spreadsheet Dr J. W. Jones provided, which was used for the model's
  original calculations. The spreadsheet is not in the repository, and no
  public copy was found.
- **A spreadsheet variant:** where the spreadsheet and the 1999 paper
  differ, the code keeps the paper's form as a comment and uses the
  spreadsheet's (below). The 1999 paper's full text was not read for this
  inventory, so its own forms are not checked here.
- **Its licence:** MIT, in the repository's `LICENSE`; the Zenodo records
  of v0.3.0 and v0.4.0 say CC BY 4.0. The mismatch is the authors' to
  settle.
- **Its versions:** v0.4.0 was used for Oliveira et al. (2024); v0.3.0
  ([doi:10.5281/zenodo.10629918](https://doi.org/10.5281/zenodo.10629918))
  for the first preprints. The model's file is unchanged since v0.1.0.
- **How it runs:** Python, with numpy, pandas, scipy and OpenCV (imported
  by the models' auxiliary module); no dependency file, tests or run
  instructions. Its runner's `main()` call is commented out, and the
  processed inputs it expects are not in the repository.

## Files

`models/model_ReducedTomgro.py` (the model, as functions; a class version
beside it), `simulations/run_Model_ReducedTomgro.py` (a run), and
`tables/parameters_inputs/tomgro_p.csv`, `tomgro_i.csv`, `tomgro_s0.csv`
(parameters, inputs, initial states).

## States and step

Jones's five: the number of main stem nodes `n`, the leaf area index
`lai`, the above-ground dry weight `w`, the fruit dry weight `wf` and the
mature fruit dry weight `wm`, updated once a day by Euler's method, in the
order N, LAI, Wm, Wf, W. Initial values n = 4, lai = 0.014, w = 0.09,
wf = 0, wm = 0 (`run_Model_ReducedTomgro.py` 39–43).

## Drivers

An hourly table, 24 rows a day (days without 24 are dropped): `tmean`, the
hour's mean air temperature (°C); `rad`, the hour's mean PPFD inside the
greenhouse (µmol m⁻² s⁻¹); `co2` (ppm); and `hour`.

- **Gross photosynthesis, maintenance respiration and the node rate** are
  worked out hour by hour from that hour's temperature and PPFD, and
  summed into the day's rates (`model_ReducedTomgro.py` 74–94, 121–124,
  167–170, 371).
- **CO₂ is read once a day:** the day's first hour (line 63).
- **The daytime temperature** is the mean of the hours with light, or of
  hours 6 to 19 (`auxiliary_functions/f_aux.py` 689–717).
- **Inputs per experiment:** `D` (2.59, converting gross photosynthesis
  from µmol CO₂ m⁻² s⁻¹), `TRGH` (1, "inferred"), `ro` (the plants per m²)
  and `LAI_max` (`tomgro_i.csv`).

## Parameters

The `gnvman` set, labelled "original", the developers' calibration for
their Gainesville data; `av`, labelled "orig", lacks `tau2`. The file has
no unit column; the units shown are those of Oliveira et al.'s preprint
(Table A1) where it gives them.

| Parameter | `gnvman` | Unit |
| --- | --- | --- |
| `alpha_F` | 0.8 | fraction d⁻¹ |
| `beta` | 0.169 | node⁻¹ |
| `delta` | 0.038 | m² leaf node⁻¹ |
| `DFmax` | 0.08 | d⁻¹ |
| `E` | 0.75 | g dry weight g⁻¹ CH₂O |
| `K` | 0.58 | – |
| `K_F` | 5 | nodes |
| `m` | 0.1 | – |
| `N_b` | 16 | node |
| `N_FF` | 22 | node |
| `N_max` | 0.5 | node d⁻¹ |
| `p_1` | 2 | g leaf node⁻¹ |
| `Q10` | 1.4 | – |
| `Qe` | 0.08 | µmol CO₂ µmol⁻¹ photon |
| `rm` | 0.016 | applied as `rm / 24` an hour |
| `sl_N1`, `sl_N2`, `sl_R` | 0.025, 0.05, 0.0032 | – |
| `T_crit` | 24.4 | °C |
| `tau1`, `tau2` | 0.07428, 0.05848 | (`LFmax` in µmol m⁻² s⁻¹) |
| `tmaxPg`, `tmin_fr_gr`, `TSlop` | 35, 8.5, 20.6 | °C |
| `V` | 0.135 | node⁻¹ |
| `V_max` | 8 | g dry weight node⁻¹ |

Whether this set is the 1999 paper's table is not checked: the paper was
not read.

## Where it departs from the 1999 paper, as its code says

- The fruit growth's temperature factor bounded,
  `max(0.09, min(1, 1 - 0.154 * (Tdaytime - T_crit)))` (196–203).
- The fruit's maturing rate a line, `min(1, 0.0714 * (Tavg - 9))`, in place
  of an interpolation table, "good enough" (566–576).
- `Qe` a constant; its temperature dependence commented out (85).
- `LFmax` rounded (72).
- The logistic and linear forms of PGRED, fR_N, fN_T, λ and fF as the
  spreadsheet writes them (222–341).
- CO₂ the day's first hour's (63).
- The above-ground growth (`rate_aboveground`, 464–476): `p_1` zero while
  LAI is below `LAI_max`, and the first expression for `dW` overwritten by
  the second.

## Its Vanthoor implementation

`models/model_Vanthoor.py` is a different variant from GreenLight's (see
the [Vanthoor inventory](vanthoor-katzin-inventory.md)): fruit in
development stages, with their numbers; a hard switch on the buffer; its
own leaf pruning and harvest; a relative growth rate worked out from the
biomass; an hourly Euler step. As written, its `TCan24` follows the hour's
temperature rather than the last day's mean; that reading is ours, from
the code. It is not a reference for GreenLight's variant.
