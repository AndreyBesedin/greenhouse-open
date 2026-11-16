# 0083: A baseline is a policy with its provenance and a reference test

**Status:** Proposed, with [P25](../roadmap/p25-measures-and-baselines.md)'s plan
**Date:** 2026-11-16

## Context

- **Decision 0061 asks for a portfolio of baselines,** each named with its
  source and version, how faithful it is (exact, adapted or a proxy), its
  parameters, its sensors and actions, and a reference test: the example's
  rule as a smoke test; an observation-driven conventional controller as
  the matched baseline; documented grower practice as a labelled proxy,
  never a counterfactual; published controllers once their sources are
  checked; and the climate controller's loops, which read the true air, as
  a labelled privileged reference.
- **What exists:** example 03's rule, and the controller's loops (P11.2,
  decision 0058), exploratory heuristics by their own module's words. No
  baseline has a source recorded beside it.
- **The sources' licences differ** (the
  [policy evaluation memo](../research/policy-evaluation-contract.md)):
  GreenLight is BSD 3-Clause Clear; GreenLight-Gym is AGPL-3.0; several
  published controllers' code has no licence. AGC4's data are CC BY 4.0.
- **A policy is already made from an entry** (P23): a factory by its
  import path, its settings and its seed, which an episode's record names.

## Decision

- **A baseline is a policy like any other:** the protocol's `Policy`, made
  from a `PolicyEntry`, reading only its port. Baselines live in
  `greenhouse_sim.baselines`, which the dependency test holds to what the
  policy port's modules may import.
- **Each carries a provenance file** beside its code, read through a
  schema:
  - its name and version, and its source: the publication or dataset, its
    DOI or address, its licence, its version or commit, and the file or
    section its rules come from;
  - its fidelity: *exact*, *adapted* with each departure listed, *proxy*,
    or *own rule*;
  - its information: *matched*, *privileged* (it reads what no policy
    may), or *oracle*;
  - its parameters, each with its value, unit and source;
  - the sensors it reads and the actions it gives;
  - its reference test, by name.
- **A reference test holds it to its source** on the same inputs: a
  published controller's levels against the source's own functions, its
  expected values generated apart and committed as decision 0063 has it;
  a rule of the repository's own against levels worked out by hand.
- **Privileged and oracle references are reported beside** the matched
  baselines, never ranked with them.
- **A logged trace of a grower's setpoints is a proxy,** labelled so, and
  never compared as a counterfactual.
- **Code is written from its source,** or ported with its licence's notice
  where the licence allows; nothing under the AGPL or with no licence is
  copied. Data are fetched, never committed, unless decision 0063 says
  otherwise.
- **Its settings come from its source,** or are tuned on a benchmark's
  tuning conditions only, with the tuning recorded (decision 0081).

## Consequences

- **A result names what each baseline is:** a reader sees where a rule
  comes from, how far it departs from it, and what it could see.
- **A version moves when its provenance's parameters move,** as the
  policy's identity names it in every episode's record.
- **Adding a baseline is a recipe:** its code, its provenance file, its
  reference test.
- **What it costs:** a published controller is a reproduction of its own,
  with its source checked before it is compared.
- **Worth revisiting:** if a baseline cannot be held to its source on
  the same inputs, such as one whose source publishes no function to
  compare with; or if a remote baseline needs its provenance served rather
  than packaged.
