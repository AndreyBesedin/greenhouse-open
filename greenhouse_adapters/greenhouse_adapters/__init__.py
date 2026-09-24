"""Turning external greenhouse data into canonical domain records.

Everything dataset-specific (archive layouts, column names, unit quirks)
stays inside an adapter package under greenhouse_adapters/wur/...; what comes out is
the same Observation / Event / GreenhouseDescription records any producer
emits, so nothing downstream needs to know where a record came from.
Adapters stop at canonical records; what a consumer loads them into, and
what it derives from them, is the consumer's business.
"""
