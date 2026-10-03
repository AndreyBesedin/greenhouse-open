# Copilot code review instructions

Review for high-signal problems. Do not spend review comments on formatting,
import ordering or other issues Ruff/pre-commit already enforces.

Prioritize, in order:

1. Correctness bugs, broken edge cases, invalid assumptions and unsafe failure modes.
2. Violations of repository/package boundaries.
3. Missing or weak tests for changed behavior.
4. Determinism and reproducibility regressions in simulation code.
5. Public-contract compatibility and dependency changes.
6. Performance issues only when they are material at realistic simulator scale.
7. Readability or maintainability issues that are substantial enough to justify
   changing the code before merge.

Repository invariants:

- `greenhouse_protocol` is the shared contract layer and must not depend on
  other repository packages.
- `greenhouse_sim` core must remain usable without a server, database or
  browser. UI/API code may depend on the simulator, not the reverse.
- Simulated hidden truth must not leak into policy-facing observations.
  Ground truth is evaluation-only.
- Stochastic simulation changes must remain reproducible from explicit seeds.
- New runtime dependencies must be declared by the package that imports them.
- Do not introduce generic dumping-ground modules such as `utils.py`,
  `helpers.py`, `common.py` or `misc.py` when a domain-specific owner exists.
- Avoid speculative abstractions. Prefer a narrow interface tied to a real
  boundary or second implementation.
- Numbers that encode model assumptions, rates, thresholds, ranges or unit
  conversions are named constants (see "Name the numbers that carry meaning"
  in `docs/engineering.md`). A check enforces this for literals in arithmetic
  and comparisons; flag what it cannot see, such as a meaningful value passed
  as a keyword argument or hard-coded as a field default where a scenario
  should be able to change it.
- A behavior change should include a test. A refactor should preserve the
  relevant characterization unless the behavior change is intentional.
- Do not commit credentials, private code references, private design artifacts,
  or downloaded dataset contents.

Scope review:

- Flag unrelated cleanup mixed into a feature.
- Flag structural refactors mixed with behavior changes when they can reasonably
  be separated.
- If a pull request is difficult to review as one coherent change, recommend a
  concrete split by observable milestone.

When leaving inline comments, prefer actionable issues that could change the
merge decision. Put optional suggestions in the overall review summary instead
of creating many low-value threads.
