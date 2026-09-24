"""Adapter for the 2023 Autonomous Greenhouse Challenge pre-trial dataset
(greenhouse_adapters/manifests/wur_agc4-pretrial-2023.json): one compartment of dwarf
tomatoes under four light and two EC treatments, with a 5-minute climate
workbook, weekly crop measurements, destructive harvests, and (not ingested
here) canopy and single-plant RGB-D imagery."""

from greenhouse_adapters.wur.datasets import AGC4_PRETRIAL_2023

DATASET = AGC4_PRETRIAL_2023
SOURCE_ID = DATASET.id
TIMESERIES_ARTIFACT = "4th_autonomous_greenhouse_challenge_dwarf_tomato_pretrial_Timeseries.zip"
CLIMATE_MEMBER = "ClimateTimeseries.xlsx"
CROP_MEMBER = "CropMeasurements.xlsx"
DESTRUCTIVE_MEMBER = "DestructiveHarvest.xlsx"
