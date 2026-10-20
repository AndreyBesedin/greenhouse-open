// Generated from greenhouse_sim/services/plants_light.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

export const PLANTS_LIGHT_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "description": "The light on each of a scenario's plants at a moment of a run, in\nseconds from its start: its PAR then, in µmol/m²/s, and its daily light\nintegral on the day the moment belongs to (`greenhouse_sim.core.clock`),\nin mol/m²/d, by plant.",
  "properties": {
    "time_s": {
      "title": "Time S",
      "type": "number"
    },
    "par_umol_m2_s": {
      "additionalProperties": {
        "type": "number"
      },
      "title": "Par Umol M2 S",
      "type": "object"
    },
    "daily_light_integral_mol_m2_d": {
      "additionalProperties": {
        "type": "number"
      },
      "title": "Daily Light Integral Mol M2 D",
      "type": "object"
    }
  },
  "required": [
    "time_s",
    "par_umol_m2_s",
    "daily_light_integral_mol_m2_d"
  ],
  "title": "PlantsLight",
  "type": "object"
};
