"""Which time-series columns become which ObservationType.

Units are as declared in the dataset's channel_info.json, which already match
the domain's unit conventions (degree_Celsius, percent, ppm, umol/m2/s,
g/m3, minute, L/m2, dS/m, W/m2, J/cm2, m/s) - so no conversion is needed,
only selection.

Not ingested yet from the compartment files: per-sensor extras (substrate
probes and single-team sensors), which need sensor identity kept per probe.
The per-pot cost columns are skipped: each is the per-m2 cost times the pot
area.

Energy and cost columns are increments over the 5 minutes ending at the row,
per m2 of greenhouse. Cost per m2 divided by the energy column is a constant
price (heating EUR 0.025/MJ, CO2 EUR 0.3/kg, lighting EUR 0.2-0.3/kWh), so the
energy columns are per m2 too, even where channel_info omits the area. The
source writes 1e-10 for zero.

The `*_vip` channels are ingested as effective control values, separate from
their setpoints: they differ far more than "value in process" suggests (CO2
matches its setpoint only 62% of the time, up to 1114 ppm apart; irrigation
interval 67%). CO2 dosing minutes reset daily around 07:40 local, not at
midnight, so the value is minutes since the controller's reset.

`dwarf_tomato/harvest_date` is read separately, as the final-harvest instant
(timeseries.final_harvest_timestamp); `dwarf_tomato/pot_area` is skipped as
the exact reciprocal of plant density.

Deliberately not ingested from the site files, for temporal honesty (a
record must not reveal at time T what was only known later), as measured on
2026-09-14:

- `weather/wind_direction.registration` holds eight bit-flag values (1, 2, 4
  ... 128), not the degrees its channel_info claims, and nothing in the
  dataset says which flag is which compass sector. Unknown stays unknown.
- The hourly `weather_forecast/*` fields (temperature, humidity, radiation,
  wind, cloudiness) are indexed by the time the forecast is valid for, not
  when it was issued: forecast temperature at t tracks measured temperature
  at t to 0.66 degC MAE, closer than at any lag. With no issue time, a replay
  at T cannot know which of them existed at T. Only the daily radiation-sum
  forecast is ingested: it is a running value for the current local day,
  revised during the day and converging on that day's measured total, so the
  row at t is read as "the forecast as known at t"."""

from greenhouse_protocol.enums import ObservationType

TIME_COLUMN = "time"
WEATHER_MEMBER = "timeseries/weather.csv"
FORECAST_MEMBER = "timeseries/weather_forecast.csv"
# The day of year of a compartment's final harvest, written once, on the
# harvest day's last row of that compartment's file.
HARVEST_DAY_COLUMN = "dwarf_tomato/harvest_date"

CHANNELS: dict[str, ObservationType] = {
    # measured climate
    "compartment/air_temperature": ObservationType.AIR_TEMPERATURE_C,
    "compartment/relative_humidity": ObservationType.RELATIVE_HUMIDITY_PCT,
    "compartment/humidity_deficit": ObservationType.HUMIDITY_DEFICIT_G_M3,
    "compartment/co2_concentration": ObservationType.CO2_PPM,
    "compartment/par": ObservationType.PAR_UMOL_M2_S,
    "compartment/heating_lower_circuit/pipe_temperature": (
        ObservationType.HEATING_PIPE_TEMPERATURE_C
    ),
    # actuator state
    "compartment/screen_energy/screen_position": ObservationType.ENERGY_SCREEN_POSITION_PCT,
    "compartment/screen_blackout/screen_position": ObservationType.BLACKOUT_SCREEN_POSITION_PCT,
    "compartment/window_position_lee_side": ObservationType.WINDOW_POSITION_LEE_PCT,
    "compartment/window_position_wind_side": ObservationType.WINDOW_POSITION_WIND_PCT,
    "compartment/lamps_activation_percentage": ObservationType.LAMPS_ACTIVATION_PCT,
    # recorded control setpoints
    "compartment/heating_temperature_setpoint": ObservationType.HEATING_TEMPERATURE_SETPOINT_C,
    "compartment/ventilation_temperature_setpoint": (
        ObservationType.VENTILATION_TEMPERATURE_SETPOINT_C
    ),
    "compartment/co2_concentration_setpoint": ObservationType.CO2_SETPOINT_PPM,
    "compartment/humidity_deficit_setpoint": ObservationType.HUMIDITY_DEFICIT_SETPOINT_G_M3,
    "compartment/lamps_activation_percentage_setpoint": (
        ObservationType.LAMPS_ACTIVATION_SETPOINT_PCT
    ),
    "compartment/screen_energy/screen_position_setpoint": (
        ObservationType.ENERGY_SCREEN_SETPOINT_PCT
    ),
    "compartment/screen_blackout/screen_position_setpoint": (
        ObservationType.BLACKOUT_SCREEN_SETPOINT_PCT
    ),
    "compartment/water_supply/water_supply_interval_setpoint": (
        ObservationType.IRRIGATION_INTERVAL_SETPOINT_MIN
    ),
    "compartment/minimum_pipe_temperature_setpoint": (
        ObservationType.MINIMUM_PIPE_TEMPERATURE_SETPOINT_C
    ),
    "compartment/minimum_window_position_lee_side_setpoint": (
        ObservationType.MINIMUM_WINDOW_POSITION_LEE_SETPOINT_PCT
    ),
    # effective control values ("VIP": setpoint plus the controller's influences)
    "compartment/heating_temperature_vip": ObservationType.HEATING_TEMPERATURE_EFFECTIVE_C,
    "compartment/ventilation_temperature_lee_side_vip": (
        ObservationType.VENTILATION_TEMPERATURE_LEE_EFFECTIVE_C
    ),
    "compartment/ventilation_temperature_wind_side_vip": (
        ObservationType.VENTILATION_TEMPERATURE_WIND_EFFECTIVE_C
    ),
    "compartment/co2_concentration_vip": ObservationType.CO2_EFFECTIVE_PPM,
    "compartment/humidity_deficit_vip": ObservationType.HUMIDITY_DEFICIT_EFFECTIVE_G_M3,
    "compartment/screen_energy/screen_position_vip": ObservationType.ENERGY_SCREEN_EFFECTIVE_PCT,
    "compartment/screen_blackout/screen_position_vip": (
        ObservationType.BLACKOUT_SCREEN_EFFECTIVE_PCT
    ),
    "compartment/water_supply/water_supply_interval_vip": (
        ObservationType.IRRIGATION_INTERVAL_EFFECTIVE_MIN
    ),
    "compartment/minimum_pipe_temperature_vip": (
        ObservationType.MINIMUM_PIPE_TEMPERATURE_EFFECTIVE_C
    ),
    "compartment/minimum_window_position_lee_side_vip": (
        ObservationType.MINIMUM_WINDOW_POSITION_LEE_EFFECTIVE_PCT
    ),
    # CO2 dosing
    "compartment/co2_actuation_state": ObservationType.CO2_DOSING_ON,
    "compartment/co2_dosage_minutes_cumulative": ObservationType.CO2_DOSING_MINUTES_SINCE_RESET,
    # irrigation
    "compartment/water_supply/water_flow_duration": ObservationType.IRRIGATION_FLOW_DURATION_MIN,
    "compartment/water_drain/water_volume": ObservationType.DRAIN_WATER_VOLUME_L_M2,
    "compartment/water_drain/ec": ObservationType.DRAIN_EC_DS_M,
    "compartment/water_drain/ph": ObservationType.DRAIN_PH,
    # crop layout: recorded only on the day a density takes effect
    "dwarf_tomato/plant_density": ObservationType.PLANT_DENSITY_PER_M2,
}

# Per-interval increments, per m2. Reconstruction sums them into local-day
# totals (domain/accumulation.py) instead of keeping the latest value.
INCREMENT_CHANNELS: dict[str, ObservationType] = {
    "energy/energy_use.heating": ObservationType.HEATING_ENERGY_INCREMENT_MJ_M2,
    "energy/electricity_use.lighting": ObservationType.LIGHTING_ELECTRICITY_INCREMENT_KWH_M2,
    "energy/co2_dosage": ObservationType.CO2_DOSED_INCREMENT_KG_M2,
    "economics/heating_costs.per_m2": ObservationType.HEATING_COST_INCREMENT_EUR_M2,
    "economics/lighting_costs.per_m2": ObservationType.LIGHTING_COST_INCREMENT_EUR_M2,
    "economics/co2_costs.per_m2": ObservationType.CO2_COST_INCREMENT_EUR_M2,
    "economics/fixed_costs.per_m2": ObservationType.FIXED_COST_INCREMENT_EUR_M2,
}
CHANNELS.update(INCREMENT_CHANNELS)

# Channels whose positive values at or below ZERO_PLACEHOLDER_MAX are the
# source's stand-in for zero.
ZERO_PLACEHOLDER_CHANNELS = frozenset(INCREMENT_CHANNELS)
ZERO_PLACEHOLDER_MAX = 1e-9

# Channels whose source codes are recoded to domain values. A code that is
# not listed is refused rather than guessed.
RECODED: dict[str, dict[float, float]] = {
    # channel_info: "1 = on, 2 = out"
    "compartment/co2_actuation_state": {1.0: 1.0, 2.0: 0.0},
}

WEATHER_CHANNELS: dict[str, ObservationType] = {
    "weather/air_temperature.outside": ObservationType.OUTSIDE_AIR_TEMPERATURE_C,
    "weather/relative_humidity.outside": ObservationType.OUTSIDE_RELATIVE_HUMIDITY_PCT,
    "weather/humidity_deficit": ObservationType.OUTSIDE_HUMIDITY_DEFICIT_G_M3,
    "weather/air_absolute_humidity_content.outside": (
        ObservationType.OUTSIDE_ABSOLUTE_HUMIDITY_G_M3
    ),
    "weather/radiation_global": ObservationType.OUTSIDE_GLOBAL_RADIATION_W_M2,
    "weather/radiation_sum": ObservationType.OUTSIDE_RADIATION_SUM_J_CM2,
    "weather/wind_speed": ObservationType.OUTSIDE_WIND_SPEED_M_S,
    "weather/rain_state": ObservationType.OUTSIDE_RAIN,
    "weather/par.outside": ObservationType.OUTSIDE_PAR_UMOL_M2_S,
    "weather/heat_emission": ObservationType.OUTSIDE_HEAT_EMISSION_W_M2,
}

FORECAST_CHANNELS: dict[str, ObservationType] = {
    "weather_forecast/radiation_sum": ObservationType.FORECAST_RADIATION_SUM_TODAY_J_CM2,
}
