# Guidance for coding agents and Codex code review

This repository values **clear, reusable, well-tested code and fast iteration**.
Codex review should act as a thoughtful maintainer, not a second linter.
Apply these instructions to changes in this repository, including generated code.

Read only the policies relevant to the change:
- [Engineering conventions](docs/engineering.md) for review process, code style,
  tests, APIs, architecture and change discipline.
- [Accepted decisions](docs/decisions/README.md) for established technical
  boundaries; follow a superseding decision where one exists.
- [Roadmap](docs/roadmap/README.md) when a PR implements or changes a project step.
- [Contributing](CONTRIBUTING.md) for the DCO, package boundaries and PR process.
- [Copilot instructions](.github/copilot-instructions.md) for compatible
  repository invariants. Codex should complement, not duplicate, Copilot.
- [Address-review skill](.claude/skills/address-review/SKILL.md) when answering
  a review of a pull request: how to judge findings, fix with regression tests,
  reply on and resolve threads, and keep the risk gate's tick honest.
- [Release skill](.claude/skills/release/SKILL.md) when making a release:
  who may, the version, the changelog from the pull requests merged, the
  release pull request, the demo video, and the owner's tag, which CI
  publishes (decisions 0045, 0056).

## Working in this repository

What to run, what not to edit by hand, and where a change belongs; the
rules themselves are in the documents above.

### Before a commit, and before a push

```bash
uv run pre-commit run --files <the files changed>
uv run check --fast   # the pre-push hook runs it too
```

Every task is a `uv run` command (`uv run help` lists them, decision 0039),
with the workspace's own Python; `uv run setup` installs, once, what uv
does not. A change to the viewer runs `uv run viewer-checks` (lint, type
check, coverage, build) and `uv run browser-tests`, which serve the
simulator from the workspace's Python (`docs/engineering.md` says how CI
splits them into lanes). The Biome hook needs the viewer's packages, from
`uv run setup`, for any commit that touches `greenhouse_sim/web/`, a README
included.
Commits and pull request titles follow Conventional Commits
(`type(scope): summary`, decision 0002), and every commit is signed off.
Commit messages, pull request descriptions, issues, review replies, the
changelog and release notes are written for any reader of the project
and say, as far as each can hold it, what changed, why, the result, how it
was evaluated and what limits it. They leave out any one contributor's
plans, events, deadlines, commercial needs and requests, including those
of the person the agent works for
(`docs/engineering.md`, "What a public record says", decision 0044).
A pull request's description gives its changelog entry under
`## Changelog`, or `none`, and the release takes it from there; no pull
request but a release's edits `CHANGELOG.md` (decision 0056).

### Generated files

Not edited by hand; each is written by the command beside it, and a test
fails when it drifts from its source.

- `uv.lock`, every Python dependency's version for development and CI:
  `uv lock`, after a `pyproject.toml` changes (decision 0039). CI's
  `uv sync --locked` fails while it is out of step.
- The viewer's contracts, in a `generated/` folder beside the module that
  reads each, such as `greenhouse_sim/web/src/scene/generated/`: `npm run
  generate` in `greenhouse_sim/web`, from the schemas below.
- The schemas beside their models, such as
  `greenhouse_sim/greenhouse_sim/scene/snapshot.schema.json`,
  `greenhouse_sim/greenhouse_sim/scenarios/scenario.schema.json` and each
  service answer the viewer reads
  (`greenhouse_sim/tests/test_published_schemas.py` lists them all), and
  the golden files under `greenhouse_sim/tests/fixtures/`: the test that
  holds each, run with `--update`, for example
  `python greenhouse_sim/tests/test_scene_schema.py --update`. The commit
  says why they moved.
- The browser's screenshot baselines: drawn by CI's visual checks, never
  locally.

### Where a change belongs

- A record producers and consumers share: `greenhouse_protocol`, which
  depends on no other package here. Its changes are the most consequential.
- Simulation: `greenhouse_sim`, organized by domain (decision 0004). The
  reference scenario runs through the climate run
  (`greenhouse_sim/greenhouse_sim/climate/`), the sun
  (`greenhouse_sim/greenhouse_sim/solar/`) and the organ-level crop
  (`greenhouse_sim/greenhouse_sim/core/crop.py`), served by
  `greenhouse_sim/greenhouse_sim/services/`. The run is the one simulator
  (decisions 0035 and 0059): every scenario, view and example goes through
  it, and a new model is a rung of one of its parts.
- An API route: the route checks the request and maps the result; the
  logic is a service's (decision 0021).
- A dataset: `greenhouse_adapters`, from a manifest to canonical records.
- A data file, such as a fixture, an expected answer or a reproduction's
  drivers: generated when needed, committed, or fetched on first use, by
  the first of decision 0063's rules that applies.
- The viewer: `greenhouse_sim/web`, which only displays what the simulator
  serves.

For the steps themselves (a scenario, a layout, a weather, a device, a
sensor kind, an air or plant model, a viewer panel, an API route), with the
files each touches and the tests to run, see the recipes in
[docs/guides](docs/guides/README.md).

## Code review: what to prioritize

CI already handles formatting, lint, types, tests and some import rules.
Review the *quality of decisions* that these checks cannot evaluate.
Look at the relevant callers and existing abstractions, not just the diff.
Prefer a few material, actionable findings to a long list of preferences.
Do not request speculative work or more documentation/tests by default.

### 1. Maintainability, cohesion and reuse

- Prefer an existing well-fitting service, helper, protocol or component to a
  second implementation of the same behavior. Check nearby modules and other
  packages before accepting new parsing, caching, validation or conversion code.
- Equally, do not demand a generic abstraction to eliminate small, clear
  duplication. Extract shared logic when it has a genuine owner and useful reuse.
- Flag mixed responsibilities, hidden coupling, unclear data flow, leaky
  boundaries, unnecessary indirection and overly clever control flow.
- Prefer a small explicit implementation to configuration layers, factories,
  registries or dependencies introduced for hypothetical future use.
- Keep new code in the domain that owns it; avoid catch-all utilities and
  one-off wrappers with no meaningful behavior.
- Assess whether a reader can change this code safely without tracing an
  excessive number of layers.

### 2. Meaningful tests, not merely passing tests

- Medium-or-higher complexity behavior should have focused tests. Treat
  branching logic, calculations, state transitions, concurrency, retries,
  parsing, serialization, protocol boundaries and non-trivial UI interactions
  as examples of this complexity, not a rigid checklist.
- Look for realistic failure and boundary cases, not just a happy path:
  empty/missing input, limits, ordering, stale data, invalid units, repeated
  calls, interrupted work and conflicting state when applicable.
- Ask whether assertions establish the intended behavior and would fail for
  a plausible wrong implementation. Avoid tests that only assert that a call
  returned, a mock was invoked, or the current implementation is mirrored.
- For bug fixes, require a regression test that captures the old failure.
  When practical, establish that it fails without the fix and passes with it.
  For new behavior, tests should distinguish the intended behavior from the
  previous or a plausible incorrect behavior. Do not demand a ritualized
  red/green demonstration for every feature.
- Test at the narrowest useful level, then add integration/contract tests where
  components must actually work together. Avoid excessive mocking, flaky
  timing assumptions and heavy end-to-end tests that obscure the failure.
- Preserve meaningful characterization tests during refactors. For stochastic
  behavior, check seeded reproducibility or statistical properties as
  appropriate; do not lock tests to incidental random draws.
- Do not ask for tests for documentation-only, mechanical or trivial changes
  without a concrete regression risk. Coverage percentages are a signal, not
  a substitute for useful assertions.

### 3. Naming and readability

- Names should say what an entity represents, who owns it and what a function
  does. Flag misleading, ambiguous or overloaded names, not subjective taste.
- In science-facing code, make quantities and units, time scales, coordinate
  frames and distinctions between state, observation and estimate clear.
- Prefer explicit types and interfaces at boundaries; avoid untyped escape
  hatches and magic defaults that hide modelling decisions.
- Comments should explain *why* something surprising is necessary, not narrate
  obvious statements. Avoid unnecessary docstrings, repeated prose and
  comments made stale by the change.

### 4. Established policies and architectural contracts

- Check relevant rules and accepted decisions before proposing a new pattern.
  Cite the specific repository policy or decision when flagging a violation.
- Keep `greenhouse_protocol` independent of producers/consumers. The simulator
  must run independently of its API, database and browser; API routes adapt
  typed services rather than contain domain logic.
- Keep hidden simulated ground truth separate from sensor observations used
  by policies; preserve stable public contracts, explicit seed-based replay,
  and correct dependency direction.
- Follow the repository's rules on meaningful named constants and configurable
  scenario parameters, even where static checks cannot infer intent.
- Flag unintentional breaking changes to public imports, schemas, units or
  on-disk representations. Prefer compatibility or an explicit migration.
- Check changes to dependency ownership, package metadata, security-sensitive
  boundaries and external/tool execution where relevant.
- Hold data files to decision 0063: flag a committed file that could be
  generated when needed, one over its size limit, a check that fetches
  what every run needs, and any publisher's dataset or reference's data
  committed at all.

### 5. Scientific grounding and model credibility

For substantive changes to plant growth, airflow/CFD, radiation, climate,
sensor physics, numerical methods or model parameters:
- Expect a traceable source in the PR or nearby modelling documentation:
  preferably a paper/DOI, authoritative technical reference or dataset.
  The reference should support the *specific* assumption or equation,
  not merely the broad topic.
- Make parameter provenance, units, valid ranges, simplifications and expected
  fidelity clear enough to assess or reproduce the result.
- Ask for suitable validation: analytical invariants, a reference case,
  calibration data, convergence/sensitivity checks or comparisons with
  published results, proportional to the model's ambition.
- An exploratory heuristic is acceptable when *explicitly labelled* as such
  with its limitations. Do not present invented constants, toy models or
  visually convincing output as scientifically validated.
- Do not demand a fresh citation for a pure refactor, routine software change
  or implementation of an already documented model.

### 6. Efficiency, simulation fluency and UX

- Challenge avoidable work on a hot path: unnecessary full re-simulations,
  repeated parsing/serialization, expensive per-frame allocations, quadratic
  loops, unbounded buffers, over-frequent events or needless synchronous work.
- Consider both simulator throughput and interactive responsiveness: smooth
  playback, rendering, navigation, progress and feedback under realistic
  greenhouse/plant/sensor counts.
- Weigh fidelity against runtime and memory. Prefer selectable fidelity and
  isolated expensive solvers over imposing high cost on every scenario.
- Flag a performance concern only with a plausible mechanism and meaningful
  scale; suggest a representative measurement when the impact is uncertain.
  Do not nitpick micro-optimizations without evidence.

### 7. Reliability, recovery and security

- Look for failures CI cannot reliably expose: races, ordering bugs, stale
  state, partial writes, leaked resources, unbounded retries, missing cleanup,
  deadlocks, dropped updates and non-idempotent recovery.
- External processes, streams, files and network calls need appropriate
  validation, timeouts, cancellation, errors and recoverable failure paths.
  Avoid silent fallbacks that make incomplete results appear valid.
- Flag credentials, private datasets or information entering public artifacts,
  unsafe input handling and surprising new dependency or license obligations.
- Flag a commit message, PR description, changelog entry or document that
  ties the work to one contributor's plans, events, deadlines, commercial needs or requests
  (decision 0044).

### 8. Scope, documentation and contributor experience

- A PR should solve one coherent problem. Flag unrelated cleanup or behavior
  changes hidden inside large mechanical refactors when they impair review.
- Check for required roadmap-step updates or decision records *when the change
  actually affects them*; do not require new documents for local implementation.
- Documentation should clarify non-obvious architecture, a scientific model's
  provenance, external constraints or the reason for a trade-off. Prefer
  self-explanatory code for everything else.
- Minimize maintenance burden: new tools, scripts, dependencies, test fixtures
  and abstraction layers all have ongoing costs.

## How to report findings

- Prioritize consequential maintainability, test-design, architecture,
  scientific, performance and reliability issues. Severity reflects impact,
  not the section where a finding appears.
- For each finding, point to the relevant changed lines, explain a realistic
  failure or maintenance cost, and propose the smallest viable remedy.
  Reference the governing policy/decision or scientific source when useful.
- Distinguish confirmed issues from hypotheses needing measurement. If a
  concern is preference-only or already enforced by CI, omit it.
- Do not block a useful PR over cosmetic style, speculative scalability,
  extra documentation or broad refactoring unrelated to its goal.
- Put optional improvements into a concise overall summary instead of
  opening many low-value inline threads.
