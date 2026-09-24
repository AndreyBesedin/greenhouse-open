"""The WUR datasets this project knows about: their upstream identity and
how their source files classify. The manifests themselves
(greenhouse_adapters/manifests/*.json) are generated from these entries."""

from dataclasses import dataclass

from greenhouse_adapters.manifests import ArtifactKind


@dataclass(frozen=True)
class WurDataset:
    id: str
    cli_name: str
    dataset_uuid: str

    def classify(self, artifact_name: str) -> ArtifactKind:
        lowered = artifact_name.lower()
        if lowered.endswith(".md"):
            return ArtifactKind.METADATA
        if "timeseries" in lowered:
            return ArtifactKind.TIMESERIES
        if "single_plant" in lowered:
            return ArtifactKind.LABELLED_IMAGES
        if "canopy" in lowered:
            return ArtifactKind.LONGITUDINAL_RGBD
        raise ValueError(f"cannot classify WUR artifact {artifact_name!r}")


AGC4_PRETRIAL_2023 = WurDataset(
    id="wur_agc4-pretrial-2023",
    cli_name="agc4-2023",
    dataset_uuid="e1ee9de9-6ce9-4502-a37c-34b5b1372bed",
)

AGC4_CHALLENGE_2024 = WurDataset(
    id="wur_agc4-challenge-2024",
    cli_name="agc4-2024",
    dataset_uuid="fa102772-32db-4b30-bace-12f2016722ce",
)

WUR_DATASETS: dict[str, WurDataset] = {
    dataset.cli_name: dataset for dataset in (AGC4_PRETRIAL_2023, AGC4_CHALLENGE_2024)
}
