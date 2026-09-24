"""Adapter for the 2024 Autonomous Greenhouse Challenge dataset
(greenhouse_adapters/manifests/wur_agc4-challenge-2024.json): six dwarf-tomato
compartments, 5-minute climate/control time series, manual harvest
workbooks, and (not ingested here) canopy RGB-D imagery."""

from greenhouse_adapters.wur.datasets import AGC4_CHALLENGE_2024

DATASET = AGC4_CHALLENGE_2024
SOURCE_ID = DATASET.id
TIMESERIES_ARTIFACT = "autonomous_greenhouse_challenge4_timeseries.zip"
TIMESERIES_MEMBER_PREFIX = "autonomous_greenhouse_challenge4_timeseries/"
