// Generated from greenhouse_sim/biology/parameter_set.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

/**
 * A crop model's parameter set, as its file gives it.
 */
export type ParameterSet = {
  /**
   * The crop model it is a set of, by its registered name.
   */
  model: "reduced_tomgro" | "vanthoor_katzin";
  /**
   * What a person calls it.
   */
  name: string;
  /**
   * Its version under its name, from 1.
   */
  version: number;
  /**
   * The set it starts from, by name, version and digest; none for a set that gives every value.
   */
  based_on: SetNamed | null;
  /**
   * The values it changes from its base, by its model's parameters' fields.
   */
  parameters: {
    [k: string]: number;
  };
  /**
   * Where each value it changes comes from, by the same fields.
   */
  why: {
    [k: string]: string;
  };
  /**
   * The version of its model it was made with.
   */
  made_for: number;
  /**
   * The cultivar it was made for; none where its source names none.
   */
  cultivar: string | null;
  description?: string;
} & (
  | {
      model?: "reduced_tomgro";
      parameters?: TomgroParameters;
    }
  | {
      model?: "vanthoor_katzin";
      parameters?: VanthoorParameters;
    }
);

/**
 * A set as another names it: its name, its version and its digest.
 */
export interface SetNamed {
  name: string;
  version: number;
  digest: string;
}
/**
 * The model's parameters (`gnvman`) and inputs (`gnv_n01`).
 */
export interface TomgroParameters {
  /**
   * alpha_F: the share of the day's net growth to the fruit, at most
   */
  alpha_f?: number;
  /**
   * β: the leaf expansion's rise with the nodes
   */
  beta?: number;
  /**
   * δ: the leaf area added with each node, at most
   */
  delta?: number;
  /**
   * DFmax: the fruit's maturing rate, at most
   */
  df_max?: number;
  /**
   * E: the conversion of CH₂O to dry weight
   */
  e?: number;
  /**
   * K: the canopy's light extinction coefficient
   */
  k?: number;
  /**
   * KF: the nodes between the first fruit and its maturing
   */
  k_f?: number;
  /**
   * m: the leaves' light transmission
   */
  m?: number;
  /**
   * Nb: the nodes at which the leaf expansion turns
   */
  n_b?: number;
  /**
   * NFF: the nodes at which the first fruit sets
   */
  n_ff?: number;
  /**
   * Nmax: the node rate, at most
   */
  n_max?: number;
  /**
   * p1: the leaf weight lost with each node once the leaf area is full
   */
  p_1?: number;
  /**
   * Q10: the maintenance respiration's rise for each 10 °C
   */
  q10?: number;
  /**
   * Qe: the leaves' quantum efficiency
   */
  qe?: number;
  /**
   * rm: the maintenance respiration
   */
  rm?: number;
  /**
   * slN1: the node rate's rise with the temperature
   */
  sl_n1?: number;
  /**
   * slN2: the node rate's fall with the temperature
   */
  sl_n2?: number;
  /**
   * slR: the roots' share's fall with the nodes
   */
  sl_r?: number;
  /**
   * Tcrit: the daytime temperature above which fruit sets less
   */
  t_crit?: number;
  /**
   * τ1: the leaves' maximum photosynthesis's rise with the CO₂, below 350 ppm
   */
  tau1?: number;
  /**
   * τ2: the leaves' maximum photosynthesis's rise with the CO₂, above 350 ppm
   */
  tau2?: number;
  /**
   * tmaxPg: the temperature above which photosynthesis falls
   */
  tmax_pg?: number;
  /**
   * tmin_fr_gr: the temperature below which fruit grows no more
   */
  tmin_fr_gr?: number;
  /**
   * TSlop: the leaf expansion's fall with the daytime temperature
   */
  t_slop?: number;
  /**
   * V: the fruit's share's rise with the nodes past the first fruit
   */
  v?: number;
  /**
   * Vmax: the dry weight added with each node, at most
   */
  v_max?: number;
  /**
   * D, an input: the conversion of gross photosynthesis from µmol CO₂ m⁻² s⁻¹ to g CH₂O m⁻² d⁻¹
   */
  d?: number;
  /**
   * TRGH, an input: the greenhouse's light transmission, 1 where the PPFD given is inside the greenhouse already, as the run's is
   */
  trgh?: number;
  /**
   * LAImax, an input: the leaf area index, at most
   */
  lai_max?: number;
  /**
   * ρ, an input: the plants per m² of floor the parameters are for
   */
  ro?: number;
}
/**
 * The model's parameters, as GreenLight's crop definition and its
 * standalone extension give them.
 */
export interface VanthoorParameters {
  /**
   * laiMax: the most leaf area
   */
  lai_max?: number;
  /**
   * alpha: the electrons from the photons the canopy absorbs
   */
  alpha?: number;
  /**
   * θ: the curvature of the electron transport's response to light
   */
  theta?: number;
  /**
   * ηCO2,AirStom: the stomata's CO₂ as a share of the air's
   */
  eta_co2_air_stom?: number;
  /**
   * cΓ: the temperature's effect on the CO₂ compensation point Γ
   */
  c_gamma?: number;
  /**
   * cFruit,m: the fruit's maintenance respiration
   */
  c_fruit_m?: number;
  /**
   * cLeaf,m: the leaves' maintenance respiration
   */
  c_leaf_m?: number;
  /**
   * cStem,m: the stems' maintenance respiration
   */
  c_stem_m?: number;
  /**
   * cFruit,g: the fruit's growth respiration, of its growth
   */
  c_fruit_g?: number;
  /**
   * cLeaf,g: the leaves' growth respiration, of their growth
   */
  c_leaf_g?: number;
  /**
   * cStem,g: the stems' growth respiration, of their growth
   */
  c_stem_g?: number;
  /**
   * cRGR: the maintenance respiration's regression coefficient
   */
  c_rgr?: number;
  /**
   * cBuf,max: the most carbohydrate in the buffer
   */
  c_buf_max?: number;
  /**
   * cBuf,min: the least carbohydrate in the buffer
   */
  c_buf_min?: number;
  /**
   * EJ: the electron transport's activation energy
   */
  e_j?: number;
  /**
   * H: the electron transport's deactivation energy
   */
  h?: number;
  /**
   * S: the electron transport's entropy
   */
  s?: number;
  /**
   * J25Leaf,max: the most electron transport at 25 °C
   */
  j25_leaf_max?: number;
  /**
   * MCH2O: the molar mass of CH₂O
   */
  m_ch2o?: number;
  /**
   * rgFruit: the fruit's potential growth
   */
  rg_fruit?: number;
  /**
   * rgLeaf: the leaves' potential growth
   */
  rg_leaf?: number;
  /**
   * rgStem: the stems' potential growth
   */
  rg_stem?: number;
  /**
   * SLA: the specific leaf area
   */
  sla?: number;
  /**
   * T25K: the electron transport's reference temperature
   */
  t25k?: number;
  /**
   * TEndSum: the temperature sum to a fully generative crop
   */
  t_end_sum?: number;
  /**
   * Q10m: the maintenance respiration's rise for each 10 °C
   */
  q10m?: number;
  /**
   * TCan,min: the instantaneous temperature below which growth is inhibited
   */
  t_can_min?: number;
  /**
   * TCan,max: the instantaneous temperature above which growth is inhibited
   */
  t_can_max?: number;
  /**
   * TCan24,min: the last day's mean temperature below which growth is inhibited
   */
  t_can24_min?: number;
  /**
   * TCan24,max: the last day's mean temperature above which growth is inhibited
   */
  t_can24_max?: number;
  /**
   * RGR: the relative growth rate, a constant, 'assumed'
   */
  rgr?: number;
  /**
   * R: the gas constant
   */
  r?: number;
  /**
   * cFruit,max: the most fruit unharvested
   */
  c_fruit_max?: number;
  /**
   * K1,PAR: the canopy's extinction of the PAR from above
   */
  k1_par?: number;
  /**
   * K2,PAR: the canopy's extinction of the PAR reflected from the floor
   */
  k2_par?: number;
  /**
   * ρCan,PAR: the canopy's reflection of PAR
   */
  rho_can_par?: number;
  /**
   * ρFlr,PAR: the floor's reflection of PAR, the Netherlands'
   */
  rho_flr_par?: number;
}
