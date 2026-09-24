"""The 2023 pre-trial ran in a single compartment, which the dataset does not
number. Its light treatments (high, medium, low, no light) are zones of tables
inside that compartment, not compartments of their own: they share one
climate."""

from greenhouse_protocol.greenhouse import Compartment, Plant

GREENHOUSE_ID = "wur_agc4_2023"
COMPARTMENT_ID = "pretrial"


def compartment(plants: list[Plant] | None = None) -> Compartment:
    return Compartment(
        compartment_id=COMPARTMENT_ID,
        name="Pre-trial compartment",
        description=(
            "The single compartment of the 2023 pre-trial; the dataset does not give its "
            "number. Tables under four light treatments (high, medium, low, no light) and "
            "two EC levels."
        ),
        plants=plants or [],
    )
