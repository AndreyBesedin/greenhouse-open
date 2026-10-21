// Generated from greenhouse_sim/services/run_manifest.schema.json by `npm run generate`.
// Do not edit: change the simulator's types and regenerate.

/**
 * What a scenario's run is made from, as QA mode shows it (P09.6): its
 * manifest's format and version, its seed and days, and the models it
 * runs, under the weather the run is asked for.
 */
export interface RunManifest {
  scenario_id: string;
  schema_version: number;
  version: string;
  random_seed: number;
  start_date: string;
  duration_days: number;
  opening_day: number | null;
  crop_model: string;
  variety: string;
  airflow: string;
  weather: string;
  weather_kind: string;
  cloud_cover_pct: number | null;
  wind_from_deg: number | null;
}
