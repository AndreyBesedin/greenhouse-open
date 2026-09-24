"""The six 2024 compartments, from the dataset README: compartment number,
the team that controlled it, its time-series file and its canopy camera.

They are six compartments of one greenhouse (the Bleiswijk trial facility),
not six greenhouses: the domain record is one Greenhouse, GREENHOUSE_ID,
whose compartments these are."""

from dataclasses import dataclass

from greenhouse_protocol.greenhouse import Compartment as DomainCompartment

GREENHOUSE_ID = "wur_agc4_2024"


@dataclass(frozen=True)
class Compartment:
    number: str  # as written in the dataset, e.g. "3.06"
    team: str
    timeseries_member: str  # csv file inside the timeseries archive
    camera: str

    @property
    def compartment_id(self) -> str:
        return self.number

    @property
    def code(self) -> str:
        """'3.06' -> '306', the form the harvest workbooks use."""
        return self.number.replace(".", "")

    @property
    def name(self) -> str:
        return f"Compartment {self.number} ({self.team})"

    def to_domain(self) -> DomainCompartment:
        return DomainCompartment(
            compartment_id=self.compartment_id,
            name=self.name,
            description=(
                f"Controlled by team {self.team} during the 2024 challenge; "
                f"canopy RGB-D camera {self.camera}."
            ),
        )


COMPARTMENTS: dict[str, Compartment] = {
    c.number: c
    for c in (
        Compartment("3.01", "Tomatonuts", "timeseries/tomatonuts.csv", "camir_27"),
        Compartment("3.02", "MuGrow", "timeseries/mugrow.csv", "cam_21"),
        Compartment("3.03", "Agrifusion", "timeseries/agrifusion.csv", "cam_20"),
        Compartment("3.06", "Reference", "timeseries/reference.csv", "cam_1"),
        Compartment("3.07", "IDEAS", "timeseries/ideas.csv", "cam_19"),
        Compartment("3.08", "Trigger", "timeseries/trigger.csv", "cam_18"),
    )
}


def compartment(number: str) -> Compartment:
    try:
        return COMPARTMENTS[number]
    except KeyError:
        raise KeyError(
            f"unknown 2024 compartment {number!r}; known: {', '.join(COMPARTMENTS)}"
        ) from None


def compartment_by_code(code: str) -> Compartment | None:
    return next((c for c in COMPARTMENTS.values() if c.code == code), None)
