"""`greenhouse-data`: the entry point for dataset work.

    greenhouse-data inventory wur agc4-2023|agc4-2024 [--write]
    greenhouse-data prepare   wur agc4-2023|agc4-2024 --profile tiny|dev|full [--compartment 3.06]

`--compartment` applies to agc4-2024, whose six compartments can be chosen;
agc4-2023 has a single compartment.

Data lives under GREENHOUSE_DATA_DIR (default ~/.greenhouse-open/data).

These commands stop at canonical records. Loading those records into a
database is the consumer's business: a consumer can add its
own subcommands to `greenhouse-data` through the `greenhouse_data.commands`
entry point group.
"""

import argparse
import sys
from collections.abc import Sequence
from importlib.metadata import entry_points
from pathlib import Path

from greenhouse_adapters.manifests import (
    ArtifactKind,
    DatasetManifest,
    load_manifest,
    manifest_path,
    write_manifest,
)
from greenhouse_adapters.profiles import PROFILES, Profile
from greenhouse_adapters.storage.layout import DataDirectory
from greenhouse_adapters.storage.resolver import (
    ArtifactResolver,
    ArtifactUnavailable,
    UpstreamHttpMirror,
)
from greenhouse_adapters.storage.upstream_4tu import build_manifest, fetch_dataset_metadata
from greenhouse_adapters.wur.agc4_challenge_2024 import build as agc4_2024
from greenhouse_adapters.wur.agc4_challenge_2024.compartments import COMPARTMENTS, compartment
from greenhouse_adapters.wur.agc4_pretrial_2023 import build as agc4_2023
from greenhouse_adapters.wur.datasets import AGC4_CHALLENGE_2024, WUR_DATASETS, WurDataset

type Commands = argparse._SubParsersAction[argparse.ArgumentParser]


# Other installed packages can add subcommands by declaring an entry point
# in this group whose target takes the subparsers object, for example
#     [project.entry-points."greenhouse_data.commands"]
#     load = "mypackage.cli:add_load_command"
COMMAND_PLUGINS = "greenhouse_data.commands"


def main(argv: Sequence[str] | None = None) -> int:
    parser, commands = build_parser()
    add_dataset_commands(commands)
    for plugin in entry_points(group=COMMAND_PLUGINS):
        plugin.load()(commands)
    return run(parser, argv)


def build_parser() -> tuple[argparse.ArgumentParser, Commands]:
    parser = argparse.ArgumentParser(prog="greenhouse-data")
    commands = parser.add_subparsers(dest="command", required=True)
    return parser, commands


def run(parser: argparse.ArgumentParser, argv: Sequence[str] | None) -> int:
    args = parser.parse_args(argv)
    handler = args.handler
    result: int = handler(args)
    return result


def add_dataset_commands(commands: Commands) -> None:
    """`inventory` and `prepare`: everything up to canonical records."""
    inventory = commands.add_parser(
        "inventory",
        help="query the upstream metadata API and generate/verify a dataset manifest "
        "(metadata only - downloads nothing else)",
    )
    add_wur_dataset_arguments(inventory)
    inventory.add_argument(
        "--write",
        action="store_true",
        help="write the generated manifest into the package (default: only compare)",
    )
    inventory.set_defaults(handler=_inventory)

    prepare = commands.add_parser(
        "prepare",
        help="fetch the artifacts a profile allows and build canonical records "
        "(tiny/dev: tabular data only, never the image archives)",
    )
    add_wur_dataset_arguments(prepare)
    prepare.add_argument("--profile", type=Profile, choices=list(Profile), required=True)
    prepare.add_argument(
        "--compartment",
        action="append",
        choices=sorted(COMPARTMENTS),
        help="2024 compartment(s) to build (default: tiny -> 3.06 only, dev/full -> all)",
    )
    prepare.add_argument("--data-dir", type=Path, default=None, help="override GREENHOUSE_DATA_DIR")
    prepare.set_defaults(handler=_prepare)


def add_wur_dataset_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("provider", choices=["wur"])
    parser.add_argument("dataset", choices=sorted(WUR_DATASETS))


def wur_dataset(args: argparse.Namespace) -> WurDataset:
    return WUR_DATASETS[args.dataset]


def _inventory(args: argparse.Namespace) -> int:
    dataset = wur_dataset(args)
    metadata = fetch_dataset_metadata(dataset.dataset_uuid)
    generated = build_manifest(
        dataset_id=dataset.id,
        dataset_uuid=dataset.dataset_uuid,
        classify=dataset.classify,
        metadata=metadata,
    )
    _print_manifest(generated)

    path = manifest_path(dataset.id)
    if args.write:
        write_manifest(generated)
        print(f"\nwrote {path}")
        return 0
    if not path.exists():
        print(f"\nno committed manifest at {path}; re-run with --write to create it")
        return 1
    committed = load_manifest(dataset.id)
    if committed == generated:
        print(f"\ncommitted manifest {path} matches upstream")
        return 0
    print(f"\ncommitted manifest {path} differs from upstream; re-run with --write to update")
    return 1


def _print_manifest(manifest: DatasetManifest) -> None:
    total = sum(artifact.size_bytes for artifact in manifest.artifacts)
    print(f"{manifest.title} (v{manifest.version}, {manifest.licence}, doi:{manifest.source.doi})")
    for artifact in manifest.artifacts:
        print(
            f"  {artifact.kind.value:18} {_human_size(artifact.size_bytes):>10}  "
            f"md5={artifact.md5}  {artifact.name}"
        )
    print(f"  total {_human_size(total)} compressed")


def _human_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} GB"


def refuse_compartments_outside_2024(dataset: WurDataset, compartments: list[str] | None) -> None:
    if dataset is not AGC4_CHALLENGE_2024 and compartments:
        raise SystemExit(
            f"{dataset.cli_name}: --compartment applies to agc4-2024 only; "
            f"{dataset.cli_name} has a single compartment"
        )


def canonical_directory(dataset: WurDataset, data_dir: DataDirectory) -> Path:
    if dataset is AGC4_CHALLENGE_2024:
        return agc4_2024.canonical_directory(data_dir)
    return agc4_2023.canonical_directory(data_dir)


def _prepare(args: argparse.Namespace) -> int:
    dataset = wur_dataset(args)
    refuse_compartments_outside_2024(dataset, args.compartment)
    rules = PROFILES[args.profile]
    manifest = load_manifest(dataset.id)
    data_dir = DataDirectory(args.data_dir)
    resolver = ArtifactResolver(
        data_dir, mirrors=[UpstreamHttpMirror()], max_download_bytes=rules.max_download_bytes
    )

    print(f"profile {rules.profile.value}: data directory {data_dir.root}")
    for artifact in manifest.artifacts:
        if artifact.kind not in rules.artifact_kinds:
            print(f"  skip   {artifact.name} ({artifact.kind.value}: not part of this profile)")
            continue
        try:
            path = resolver.resolve(manifest, artifact.name)
        except ArtifactUnavailable as error:
            print(f"  error  {error}")
            return 1
        print(f"  ready  {path}")

    if ArtifactKind.TIMESERIES not in rules.artifact_kinds:
        return 0
    if dataset is AGC4_CHALLENGE_2024:
        numbers = args.compartment or (
            ["3.06"] if rules.profile == Profile.TINY else sorted(COMPARTMENTS)
        )
        canonical = agc4_2024.build_greenhouse(
            data_dir, resolver, [compartment(number) for number in numbers]
        )
        scope = f"compartments {', '.join(numbers)}"
    else:
        canonical = agc4_2023.build_greenhouse(data_dir, resolver)
        scope = "the pre-trial compartment"
    provenance = canonical.provenance()
    print(
        f"  built  {canonical.directory} {scope} "
        f"({provenance.observation_count:,} observations, {provenance.event_count} events, "
        f"{provenance.first_timestamp} .. {provenance.last_timestamp})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
