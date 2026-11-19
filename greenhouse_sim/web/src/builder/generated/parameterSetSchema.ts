// Generated from greenhouse_sim/biology/parameter_set.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const PARAMETER_SET_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$defs": {
    "SetNamed": {
      "additionalProperties": false,
      "properties": {
        "name": {
          "pattern": "^[a-z0-9][a-z0-9_]*$",
          "title": "Name",
          "type": "string"
        },
        "version": {
          "exclusiveMinimum": 0,
          "title": "Version",
          "type": "integer"
        },
        "digest": {
          "pattern": "^sha256:[0-9a-f]{64}$",
          "title": "Digest",
          "type": "string"
        }
      },
      "required": [
        "name",
        "version",
        "digest"
      ],
      "title": "SetNamed",
      "type": "object"
    },
    "TomgroParameters": {
      "additionalProperties": false,
      "properties": {
        "alpha_f": {
          "default": 0.8,
          "maximum": 1,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "a share, of all of it at most: the fruit grows by it of the day's net growth (growth.py)"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "Alpha F",
          "type": "number",
          "unit": "fraction d⁻¹"
        },
        "beta": {
          "default": 0.169,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "Beta",
          "type": "number",
          "unit": "node⁻¹"
        },
        "delta": {
          "default": 0.038,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "Delta",
          "type": "number",
          "unit": "m² leaf node⁻¹"
        },
        "df_max": {
          "default": 0.08,
          "maximum": 1,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "the day's step: a day matures DFmax of the fruit not yet mature, all of it at most (growth.py)"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "Df Max",
          "type": "number",
          "unit": "d⁻¹"
        },
        "e": {
          "default": 0.75,
          "exclusiveMinimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "E",
          "type": "number",
          "unit": "g dry weight g⁻¹ CH₂O"
        },
        "k": {
          "default": 0.58,
          "exclusiveMinimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "K",
          "type": "number",
          "unit": "-"
        },
        "k_f": {
          "default": 5,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "K F",
          "type": "number",
          "unit": "nodes"
        },
        "m": {
          "default": 0.1,
          "exclusiveMaximum": 1,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "a transmission, less than all the light: at 1 an hour with no light's photosynthesis is 0 / 0 (growth.py)"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "M",
          "type": "number",
          "unit": "-"
        },
        "n_b": {
          "default": 16,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "N B",
          "type": "number",
          "unit": "node"
        },
        "n_ff": {
          "default": 22,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "N Ff",
          "type": "number",
          "unit": "node"
        },
        "n_max": {
          "default": 0.5,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "N Max",
          "type": "number",
          "unit": "node d⁻¹"
        },
        "p_1": {
          "default": 2,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "P 1",
          "type": "number",
          "unit": "g leaf node⁻¹"
        },
        "q10": {
          "default": 1.4,
          "exclusiveMinimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "Q10",
          "type": "number",
          "unit": "-"
        },
        "qe": {
          "default": 0.08,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "Qe",
          "type": "number",
          "unit": "µmol CO₂ µmol⁻¹ photon"
        },
        "rm": {
          "default": 0.016,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "Rm",
          "type": "number",
          "unit": "d⁻¹, applied as rm / 24 an hour"
        },
        "sl_n1": {
          "default": 0.025,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "Sl N1",
          "type": "number",
          "unit": "°C⁻¹"
        },
        "sl_n2": {
          "default": 0.05,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "Sl N2",
          "type": "number",
          "unit": "°C⁻¹"
        },
        "sl_r": {
          "default": 0.0032,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "Sl R",
          "type": "number",
          "unit": "node⁻¹"
        },
        "t_crit": {
          "default": 24.4,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "T Crit",
          "type": "number",
          "unit": "°C"
        },
        "tau1": {
          "default": 0.07428,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "Tau1",
          "type": "number",
          "unit": "µmol m⁻² s⁻¹ ppm⁻¹"
        },
        "tau2": {
          "default": 0.05848,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "Tau2",
          "type": "number",
          "unit": "µmol m⁻² s⁻¹ ppm⁻¹"
        },
        "tmax_pg": {
          "default": 35,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "Tmax Pg",
          "type": "number",
          "unit": "°C"
        },
        "tmin_fr_gr": {
          "default": 8.5,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "Tmin Fr Gr",
          "type": "number",
          "unit": "°C"
        },
        "t_slop": {
          "default": 20.6,
          "exclusiveMinimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "T Slop",
          "type": "number",
          "unit": "°C"
        },
        "v": {
          "default": 0.135,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "V",
          "type": "number",
          "unit": "node⁻¹"
        },
        "v_max": {
          "default": 8,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_p.csv, set gnvman ('original'); units as their preprint's Table A1 gives them where it does",
          "title": "V Max",
          "type": "number",
          "unit": "g dry weight node⁻¹"
        },
        "d": {
          "default": 2.5926912,
          "exclusiveMinimum": 0,
          "fixed": "a conversion of units: no set changes it",
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "readOnly": true,
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_i.csv, 'all': Jones et al. 1999, spreadsheet",
          "title": "D",
          "type": "number",
          "unit": "g CH₂O s d⁻¹ µmol⁻¹ CO₂"
        },
        "trgh": {
          "default": 1,
          "fixed": "1, as the run gives the PPFD inside the greenhouse: another value would count the cover's transmission twice",
          "maximum": 1,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "a share, of all of it at most: the light the cover lets through of the light outside"
          },
          "readOnly": true,
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_i.csv, 'all': transmissivity of the cover, Jones et al. 1999, spreadsheet (inferred)",
          "title": "Trgh",
          "type": "number",
          "unit": "-"
        },
        "lai_max": {
          "default": 4,
          "exclusiveMinimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_i.csv, gnv_n01",
          "title": "Lai Max",
          "type": "number",
          "unit": "m² leaf m⁻²"
        },
        "ro": {
          "default": 3.5,
          "exclusiveMinimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Oliveira et al. v0.4.0, tables/parameters_inputs/tomgro_i.csv, gnv_n01",
          "title": "Ro",
          "type": "number",
          "unit": "plants m⁻²"
        }
      },
      "title": "TomgroParameters",
      "type": "object"
    },
    "VanthoorParameters": {
      "additionalProperties": false,
      "properties": {
        "lai_max": {
          "default": 3,
          "exclusiveMinimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 2.2, the Netherlands",
          "title": "Lai Max",
          "type": "number",
          "unit": "m² leaf m⁻² floor"
        },
        "alpha": {
          "default": 0.385,
          "exclusiveMinimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.1",
          "title": "Alpha",
          "type": "number",
          "unit": "µmol e⁻ µmol⁻¹ photons"
        },
        "theta": {
          "default": 0.7,
          "exclusiveMinimum": 0,
          "maximum": 1,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "a curvature, of the non-rectangular hyperbola: above 1 the electron transport is not a real number where light and its most are alike (growth.py)"
          },
          "source": "Vanthoor (2011), Table 9.1",
          "title": "Theta",
          "type": "number",
          "unit": "-"
        },
        "eta_co2_air_stom": {
          "default": 0.67,
          "exclusiveMinimum": 0,
          "maximum": 1,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "a share of the air's CO₂, which the stomata take theirs from: all of it at most"
          },
          "source": "Vanthoor (2011), Table 9.1",
          "title": "Eta Co2 Air Stom",
          "type": "number",
          "unit": "-"
        },
        "c_gamma": {
          "default": 1.7,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.1",
          "title": "C Gamma",
          "type": "number",
          "unit": "µmol mol⁻¹ K⁻¹"
        },
        "c_fruit_m": {
          "default": 1.16e-7,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.1",
          "title": "C Fruit M",
          "type": "number",
          "unit": "mg mg⁻¹ s⁻¹"
        },
        "c_leaf_m": {
          "default": 3.47e-7,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.1",
          "title": "C Leaf M",
          "type": "number",
          "unit": "mg mg⁻¹ s⁻¹"
        },
        "c_stem_m": {
          "default": 1.47e-7,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.1",
          "title": "C Stem M",
          "type": "number",
          "unit": "mg mg⁻¹ s⁻¹"
        },
        "c_fruit_g": {
          "default": 0.27,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.1",
          "title": "C Fruit G",
          "type": "number",
          "unit": "-"
        },
        "c_leaf_g": {
          "default": 0.28,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.1",
          "title": "C Leaf G",
          "type": "number",
          "unit": "-"
        },
        "c_stem_g": {
          "default": 0.3,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.1",
          "title": "C Stem G",
          "type": "number",
          "unit": "-"
        },
        "c_rgr": {
          "default": 2850000,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.1",
          "title": "C Rgr",
          "type": "number",
          "unit": "s (written s⁻¹; cRgr · rgr is dimensionless)"
        },
        "c_buf_max": {
          "default": 20000,
          "exclusiveMinimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.1",
          "title": "C Buf Max",
          "type": "number",
          "unit": "mg CH₂O m⁻²"
        },
        "c_buf_min": {
          "default": 1000,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.1",
          "title": "C Buf Min",
          "type": "number",
          "unit": "mg CH₂O m⁻²"
        },
        "e_j": {
          "default": 37000,
          "exclusiveMinimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.1",
          "title": "E J",
          "type": "number",
          "unit": "J mol⁻¹"
        },
        "h": {
          "default": 220000,
          "exclusiveMinimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.1",
          "title": "H",
          "type": "number",
          "unit": "J mol⁻¹"
        },
        "s": {
          "default": 710,
          "exclusiveMinimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.1",
          "title": "S",
          "type": "number",
          "unit": "J mol⁻¹ K⁻¹"
        },
        "j25_leaf_max": {
          "default": 210,
          "exclusiveMinimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.1",
          "title": "J25 Leaf Max",
          "type": "number",
          "unit": "µmol e⁻ m⁻² leaf s⁻¹"
        },
        "m_ch2o": {
          "default": 0.03,
          "exclusiveMinimum": 0,
          "fixed": "a constant of nature: no set changes it",
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "readOnly": true,
          "source": "Vanthoor (2011), Table 9.1",
          "title": "M Ch2O",
          "type": "number",
          "unit": "mg µmol⁻¹"
        },
        "rg_fruit": {
          "default": 0.328,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.1",
          "title": "Rg Fruit",
          "type": "number",
          "unit": "mg CH₂O m⁻² s⁻¹"
        },
        "rg_leaf": {
          "default": 0.095,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.1",
          "title": "Rg Leaf",
          "type": "number",
          "unit": "mg CH₂O m⁻² s⁻¹"
        },
        "rg_stem": {
          "default": 0.074,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.1",
          "title": "Rg Stem",
          "type": "number",
          "unit": "mg CH₂O m⁻² s⁻¹"
        },
        "sla": {
          "default": 0.0000266,
          "exclusiveMinimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.1",
          "title": "Sla",
          "type": "number",
          "unit": "m² leaf mg⁻¹"
        },
        "t25k": {
          "default": 298.15,
          "exclusiveMinimum": 0,
          "fixed": "the temperature J25Leaf,max is given at: another value would change what that parameter means",
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "readOnly": true,
          "source": "Vanthoor (2011), Table 9.1",
          "title": "T25K",
          "type": "number",
          "unit": "K"
        },
        "t_end_sum": {
          "default": 1035,
          "exclusiveMinimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.1, its unit changed as GreenLight's definition notes",
          "title": "T End Sum",
          "type": "number",
          "unit": "°C day"
        },
        "q10m": {
          "default": 2,
          "exclusiveMinimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.1",
          "title": "Q10M",
          "type": "number",
          "unit": "-"
        },
        "t_can_min": {
          "default": 10,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.2",
          "title": "T Can Min",
          "type": "number",
          "unit": "°C"
        },
        "t_can_max": {
          "default": 34,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.2",
          "title": "T Can Max",
          "type": "number",
          "unit": "°C"
        },
        "t_can24_min": {
          "default": 15,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.2",
          "title": "T Can24 Min",
          "type": "number",
          "unit": "°C"
        },
        "t_can24_max": {
          "default": 24.5,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 9.2",
          "title": "T Can24 Max",
          "type": "number",
          "unit": "°C"
        },
        "rgr": {
          "default": 0.000003,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "GreenLight 1's setGlParams.m, 'assumed', as GreenLight's definition cites it",
          "title": "Rgr",
          "type": "number",
          "unit": "s⁻¹"
        },
        "r": {
          "default": 8314,
          "exclusiveMinimum": 0,
          "fixed": "a constant of nature: no set changes it",
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "readOnly": true,
          "source": "Vanthoor (2011), Table 8.1 (Table 9.1 gives 8.314 J mol⁻¹ K⁻¹)",
          "title": "R",
          "type": "number",
          "unit": "J kmol⁻¹ K⁻¹"
        },
        "c_fruit_max": {
          "default": 300000,
          "exclusiveMinimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Katzin (2021), p. 246",
          "title": "C Fruit Max",
          "type": "number",
          "unit": "mg CH₂O m⁻²"
        },
        "k1_par": {
          "default": 0.7,
          "exclusiveMinimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 8.1, as the standalone extension gives it",
          "title": "K1 Par",
          "type": "number",
          "unit": "-"
        },
        "k2_par": {
          "default": 0.7,
          "exclusiveMinimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "none in its source: the field's type's"
          },
          "source": "Vanthoor (2011), Table 8.1, as the standalone extension gives it",
          "title": "K2 Par",
          "type": "number",
          "unit": "-"
        },
        "rho_can_par": {
          "default": 0.07,
          "maximum": 1,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "a share of the PAR that reaches it, all of it at most: above 1 the canopy absorbs less than none (growth.py)"
          },
          "source": "Vanthoor (2011), Table 8.1, as the standalone extension gives it",
          "title": "Rho Can Par",
          "type": "number",
          "unit": "-"
        },
        "rho_flr_par": {
          "default": 0.65,
          "maximum": 1,
          "minimum": 0,
          "range_from": {
            "least": "none in its source: the field's type's",
            "most": "a share of the PAR that reaches it, all of it at most: above 1 the canopy absorbs less than none (growth.py)"
          },
          "source": "Vanthoor (2011), Table 8.2, the Netherlands, as the standalone extension gives it",
          "title": "Rho Flr Par",
          "type": "number",
          "unit": "-"
        }
      },
      "title": "VanthoorParameters",
      "type": "object"
    }
  },
  "additionalProperties": false,
  "properties": {
    "model": {
      "title": "Model",
      "type": "string",
      "enum": [
        "reduced_tomgro",
        "vanthoor_katzin"
      ]
    },
    "name": {
      "pattern": "^[a-z0-9][a-z0-9_]*$",
      "title": "Name",
      "type": "string"
    },
    "version": {
      "exclusiveMinimum": 0,
      "title": "Version",
      "type": "integer"
    },
    "based_on": {
      "anyOf": [
        {
          "$ref": "#/$defs/SetNamed"
        },
        {
          "type": "null"
        }
      ]
    },
    "parameters": {
      "additionalProperties": {
        "type": "number"
      },
      "title": "Parameters",
      "type": "object"
    },
    "why": {
      "additionalProperties": {
        "minLength": 1,
        "type": "string"
      },
      "title": "Why",
      "type": "object"
    },
    "made_for": {
      "exclusiveMinimum": 0,
      "title": "Made For",
      "type": "integer"
    },
    "cultivar": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "title": "Cultivar"
    },
    "description": {
      "default": "",
      "title": "Description",
      "type": "string"
    }
  },
  "required": [
    "model",
    "name",
    "version",
    "based_on",
    "parameters",
    "why",
    "made_for",
    "cultivar"
  ],
  "title": "ParameterSet",
  "type": "object",
  "oneOf": [
    {
      "properties": {
        "model": {
          "const": "reduced_tomgro"
        },
        "parameters": {
          "$ref": "#/$defs/TomgroParameters"
        }
      }
    },
    {
      "properties": {
        "model": {
          "const": "vanthoor_katzin"
        },
        "parameters": {
          "$ref": "#/$defs/VanthoorParameters"
        }
      }
    }
  ]
};
