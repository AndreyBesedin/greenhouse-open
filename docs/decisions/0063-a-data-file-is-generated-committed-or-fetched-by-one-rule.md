# 0063: A data file is generated, committed or fetched, by one rule

**Status:** Proposed
**Date:** 2026-10-30

## Context

The repository keeps data beside its code: files a test compares against,
files a package or the viewer reads, and the inputs and outputs of the
research's reproductions. Each kind found its place on its own:

- **Generated files** are committed, each written by a command and held to
  its source by a test (`AGENTS.md`, "Generated files"); `.gitattributes`
  folds them in a pull request's diff.
- **Golden files** under `greenhouse_sim/tests/fixtures/` are committed and
  written again with `--update`.
- **The browser's screenshot baselines,** 27 images and 4.9 MB, the largest
  580 KB, are committed and drawn by CI (decision 0014).
- **A solved CFD result** is committed, keyed by what OpenFOAM was given, so
  that nothing else needs OpenFOAM (decision 0027).
- **The reference greenhouse's kept opening** is committed gzipped
  (190 KB), because working out the 80 days before it takes minutes (P09);
  so is the viewer's QA scene (810 KB).
- **A publisher's dataset** is never in the repository. The adapters'
  manifests name each artifact's address, size, checksum and licence, and
  their storage reads a local copy, then a configured mirror, then the
  publisher, checking the checksum (`greenhouse_adapters/README.md`).
- **A reference implementation's code and data** are run apart and not
  copied (decision 0060).

No rule says when a file is generated rather than committed, how large a
committed file may be, or where a file goes that a check needs but that is
too large to commit. The reproductions of decision 0060 found the gap: one
commits its drivers, 157 KB that its own script writes again byte for byte
in a fraction of a second, beside its reference's output (10 KB); another,
in review (#411), adds three reference outputs of 460 to 720 KB. Each was
weighed file by file.

What weighs on the choice:

- **History:** Git keeps every version of a committed file, and every clone
  and fork carries them all. The history packs to about 29 MB today, most
  of it images.
- **Offline checks:** `uv run check --fast` reads nothing from the network
  beyond the package index, and a package installed from its wheel reads
  only what the wheel holds.
- **Review:** an expected answer that changes is only reviewed where the
  pull request shows it.
- **Forks:** a pull request from a fork runs CI without the repository's
  secrets, so a file a check needs must be readable without credentials,
  by anyone.
- **Git LFS,** weighed for the larger files and left out: a clone without
  it holds pointer files in place of the data, and GitHub meters its
  storage and bandwidth, forks' included.

## Decision

Where a data file lives is decided by the first of these rules that
applies to it.

1. **Not the project's to publish: never committed.** Credentials, personal
   data, anyone's private or commercial data
   ([what a public record says](../engineering.md#what-a-public-record-says)),
   a publisher's dataset, and a reference implementation's code or data
   (decision 0060). A published dataset is fetched from its publisher, as
   in rule 4, under its own licence.
2. **Made when needed: generated, not committed,** when all of these hold:
   - it is made from what the repository holds, and nothing else;
   - deterministically, byte for byte the same on every platform that CI
     and development use;
   - in under 5 seconds on a developer's machine;
   - and nothing needs it as it is: whatever reads it can run the code
     that makes it first, and no test compares against it. A published
     schema, a golden file or a screenshot baseline is not generated so:
     made when a test runs, it would hold the code to itself, and a change
     to it would go unseen in review.

   It is computed in memory, or written to a temporary or cache folder when
   first needed. If an outside tool read it, such as a reference
   implementation run on a reproduction's drivers, its sha256 is pinned
   beside its generator, and a test holds the generator to it.
3. **Needed as it is: committed,** if each file is at most 1 MB as stored,
   and is text, text compressed as the code reads it, or an image a
   reviewer compares. This covers:
   - what a package, the viewer or a published schema reads as a file;
   - an expected answer a test compares against: a golden file, a
     reference implementation's output, a screenshot baseline;
   - what rule 2 cannot make: too slow, or needing a tool that CI's
     ordinary checks lack, such as a solved CFD case;
   - a lockfile.

   A committed file is written again by a command named where it is
   produced. A generated one is held to its source by a test and marked
   `linguist-generated` in `.gitattributes`. One an outside tool produced
   says which tool, at which version, and under which licence. A pull
   request that commits more than 1 MB of data in all lists the files and
   their sizes in its description.
4. **Needed but too large for rule 3: fetched.** It is published outside
   the Git history, where anyone can read it without an account:
   - a file a check or an example needs: as an asset of a release of this
     repository, under a tag of its own (`data-<name>-<version>`), which
     the packages' release workflow, run on `v*` tags, leaves alone. A
     changed file is a new release, never an asset replaced;
   - research data meant to be cited, such as a reproduction's inputs and
     outputs: in an archive that gives it a DOI;
   - a bucket, such as one a downstream application keeps, only as a
     mirror: never a file's source, and never needed.

   A manifest names each file's address, size, sha256 and licence. It is
   fetched on first use into `GREENHOUSE_DATA_DIR` through the adapters'
   storage: a local copy, then a configured mirror, then its source, its
   checksum checked whenever it is fetched. CI keeps that folder in its
   cache.
5. **Whatever the rule, what is needed on every run is never fetched.**
   What `uv run check --fast` reads, or a package reads at run time, is
   generated (rule 2) or committed (rule 3). A check that needs a file too
   large for either reads a committed sample of it, or is marked `slow`
   and fetches the file. What only an opt-in check or a full analysis
   reads may be fetched, and a profile caps how much, as the adapters'
   profiles do.

## Consequences

- **A file's place can be checked** against these rules, and a review cites
  the rule it applies, such as "0063, rule 2".
- **Today's files** mostly stay where they are:

  | Files | Rule | Change |
  | --- | --- | --- |
  | Lockfiles, published schemas, the viewer's generated contracts | 3 | None |
  | Golden files, screenshot baselines | 3 | None |
  | The solved CFD result, the kept opening, the QA scenes | 3 | None |
  | A recorded example day's weather (`example_day.csv`) | 3 | None |
  | Reduced-State TOMGRO's reference output (10 KB) | 3 | None |
  | Reduced-State TOMGRO's drivers (157 KB) | 2, if every platform writes them byte for byte | Generated, their sha256 kept |
  | Vanthoor's reference outputs, in review (460 to 720 KB each) | 3 | None, at a 1 MB limit |
  | The adapters' datasets | 1, fetched as in 4 | None |

- **Rule 4 has no file yet** other than the publishers' datasets. The first
  file it applies to brings a manifest for the repository's own files, the
  step that publishes them, and a check that each address in it is a data
  release of this repository or a DOI.
- **Who publishes:** a data release is a tag, which the repository's tag
  ruleset keeps to its owner. A contributor whose change needs a new large
  file attaches it to the pull request, or to a release of their fork, and
  the owner publishes it before the pull request merges.
- **Forks need no change:** they read the same files at the same
  addresses, without credentials, and so does CI on their pull requests.
- **GitHub's immutable releases** would lock a data release's assets,
  where a checksum only catches a change; but the setting covers the
  packages' releases too, so turning it on waits until their workflow is
  checked against it.
- **A large expected answer** is reduced before it is committed, to the
  steps and states a test compares, rather than fetched for every run.
- **Worth revisiting** if the history grows past about 100 MB, if a file
  every run needs outgrows rule 3, or if release assets stop being free to
  serve or a file outgrows their 2 GiB.
