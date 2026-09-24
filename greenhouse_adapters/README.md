# greenhouse-adapters

Reproducible adapters from recorded greenhouse datasets to canonical
records, and the `greenhouse-data` command. Part of
[greenhouse-open](../README.md). Apache-2.0 (the code; see below for data).

```bash
greenhouse-data inventory wur agc4-2024            # metadata only, downloads nothing else
greenhouse-data prepare wur agc4-2024 --profile tiny
```

- **Manifests** in the package describe each dataset: artifacts, sizes,
  checksums, download URLs and licence. `inventory` regenerates them from
  the publisher's metadata API and compares.
- **Storage** resolves an artifact from a local copy, then configured
  mirrors, then the publisher, verifying checksums and resuming downloads.
  A profile caps what may be downloaded: `tiny` and `dev` never fetch the
  image archives; `full` does (about 43 GB).
- **The canonical tier** is line-delimited JSON of the protocol's records
  with a provenance file (source members, checksums, content hashes). The
  same source bytes always produce the same output bytes.
- **Adapters** keep everything dataset-specific - archive layouts, column
  names, unit quirks, local time - inside `greenhouse_adapters/wur/...`.
  Values are kept as recorded, including implausible ones, and the adapter
  refuses rather than guesses where the source is ambiguous (for example,
  local times that occur twice at a daylight-saving change).

Data lives under `GREENHOUSE_DATA_DIR` (default `~/.greenhouse-open/data`),
in `raw/`, `canonical/` and `features/` tiers.

Another package can add subcommands to `greenhouse-data` through the
`greenhouse_data.commands` entry point group, for example a command that
loads canonical records into its own database.

## Datasets

No data is included in this package or repository. The adapters download
it from the publisher, and it stays under the publisher's licence.

| Dataset | Publisher | Licence | DOI |
| --- | --- | --- | --- |
| 4th Autonomous Greenhouse Challenge: Dwarf Tomato Timeseries and Images (2024) | Wageningen University & Research, via 4TU.ResearchData | CC BY 4.0 | [10.4121/fa102772-32db-4b30-bace-12f2016722ce.v1](https://doi.org/10.4121/fa102772-32db-4b30-bace-12f2016722ce.v1) |
| 4th Autonomous Greenhouse Challenge: Pre-trial Dwarf Tomato Measurements and Images (2023) | Wageningen University & Research, via 4TU.ResearchData | CC BY 4.0 | [10.4121/e1ee9de9-6ce9-4502-a37c-34b5b1372bed.v1](https://doi.org/10.4121/e1ee9de9-6ce9-4502-a37c-34b5b1372bed.v1) |

If you publish results derived from these datasets, cite them as their
publishers ask.

## Dependencies

`greenhouse-protocol`, Pydantic 2, openpyxl and httpx.
