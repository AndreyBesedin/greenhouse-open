# Engineering conventions

This repository is small enough that consistency should be intentional rather
than recovered later. The rules below favor readable, typed, testable code and
clear ownership over clever abstractions or framework ceremony.

## Change discipline

Keep changes easy to reason about and easy to revert.

- One pull request should answer one question.
- Prefer a sequence of small working commits, each described in the
  [commit message format](#commit-messages).
- Separate behavior changes from mechanical moves or large renames.
- Do not include unrelated cleanup because a file happened to be open.
- Aim for at most 500 non-generated code/config lines and 15 code/config files.
  Crossing either threshold is allowed, but triggers an explicit manual
  self-review acknowledgement.
- Changes to shared contracts, CI/review automation, package metadata, multiple
  publishable packages, or critical simulator boundaries also trigger that
  acknowledgement regardless of size.
- Add or update tests with behavior changes. Bug fixes need regression tests.
- For simulator changes, describe the observable result. As browser QA grows,
  name the scenario or visual check used to validate it.

There is deliberately no hard pull request size limit yet. Delivery speed
matters while the project is young. If large changes become routine, tighten
the gate based on actual review pain rather than an arbitrary rule.

## Commit messages

Commits follow [Conventional Commits 1.0](https://www.conventionalcommits.org/en/v1.0.0/):

```text
<type>(<scope>): <summary>

<body: why the change is needed, when the summary cannot say it>

Signed-off-by: Your Name <you@example.com>
```

For example, `refactor(sim): move the daily dynamics into biology/tomato`.

The type says what kind of change the commit is:

| Type | Use for |
| --- | --- |
| `feat` | New behavior or capability |
| `fix` | A bug fix; it comes with a regression test |
| `refactor` | A structural change with no behavior change |
| `perf` | A change made for speed or memory, with no behavior change |
| `test` | Tests only |
| `docs` | Documentation only |
| `build` | Packaging, dependencies, package metadata |
| `ci` | CI workflows, hooks and review automation |
| `style` | Formatting only |
| `chore` | Repository maintenance that fits none of the above |
| `revert` | Reverting an earlier commit |

The scope names the package or area the commit changes: `protocol`, `sim` or
`adapters` for a package, or a narrower area such as `web`, `api` or `viewer`
when that is clearer. Leave the scope out for a change across the repository.

- Write the summary in the imperative mood, starting in lower case, with no
  trailing period, and keep the whole first line within 72 characters.
- Use the body for the reason behind the change and anything a reviewer would
  otherwise have to reconstruct. Wrap it at 72 characters.
- Mark a change that breaks a package's public interface with `!` after the
  scope and a `BREAKING CHANGE:` footer that says what consumers must do,
  for example `feat(protocol)!: ...`. This matters most for
  `greenhouse_protocol`, which every producer and consumer depends on.
- Every commit carries a `Signed-off-by` trailer (see
  [CONTRIBUTING.md](../CONTRIBUTING.md#sign-your-commits-dco)).
- Give the pull request title the same format. GitHub uses it as the merge
  commit's description, and as the commit message itself when a pull request
  is squash-merged.

Commits before this convention used plain imperative summaries. They are not
rewritten.

## Roadmap and decision records

The repository explains its own direction. Anything a commit, pull request or
code comment refers to must be readable here, without access to a private
planning tool or document.

- **Roadmap projects** live in [`docs/roadmap/`](roadmap/README.md), one
  document per project. A project's document is written, or adapted from
  private planning notes, in the first pull request that implements part of
  it. It describes the goal, what must stay stable, the steps, the acceptance
  criteria and the final QA scenario.
- **Steps have public identifiers** such as `P-1.2`. Commits and pull requests
  may cite them, because the roadmap document defines them. The pull request
  that delivers a step updates its status in that document.
- **Decisions** live in [`docs/decisions/`](decisions/README.md) as short,
  numbered records. A change that sets or reverses a lasting technical
  direction records a decision in the same pull request: architecture
  boundaries, shared contracts, runtime dependencies, supported platforms or
  the development workflow. A decision is not edited after it is accepted. A
  later record supersedes it.
- **When implementation departs from the roadmap**, the pull request updates
  the roadmap document, so it stays an accurate account rather than an
  aspiration.
- **Public documents describe this open project only.** Product plans,
  business strategy, customer information and the names or internals of
  private systems stay out. Applications that build on these packages are
  "downstream applications". `tests/test_publishable.py` rejects known private
  names and citations of documents that are not in this repository. It is a
  backstop, not a substitute for writing the documents for a public reader.

## Solo-developer review policy

The default path is automated and fast:

1. Open a pull request instead of pushing feature work directly to `main`.
2. Required CI checks must pass.
3. GitHub Copilot reviews the pull request automatically and reviews new pushes.
4. Resolve or explicitly acknowledge every review conversation.
5. If the risk gate classifies the pull request as higher risk, review the full
   diff yourself and check the manual-review item in the pull request body.
   Saving the edited description runs the gate again. Re-running an earlier
   gate run does not help: it replays the description that run saw.
6. Low-risk changes may use auto-merge once the automated checks and review are
   clear. Higher-risk changes should be merged manually after the explicit
   self-review.

The number of Copilot comments is not itself a risk score. A verbose review can
produce many low-value comments, while one comment can expose a serious issue.
Treat unresolved substantive feedback and the objective diff risk as the
signals.

Copilot review should use **Balanced** effort. The repository instructions in
`.github/copilot-instructions.md` tell it to prioritize correctness,
architecture, tests and repository invariants over style nits that Ruff already
handles.

GitHub settings should require a pull request for `main`, require CI checks,
and require conversation resolution. Do not require a human approval while the
repository has one developer. Copilot auto-approval can be enabled later if it
proves useful, but the workflow should not depend on a preview feature.

## Code structure

Names should explain ownership.

- Put code next to the domain concept that owns it.
- Prefer specific modules such as `ripening.py`, `radiation.py` or
  `checkpoints.py` over generic `utils.py`, `helpers.py`, `common.py` or
  `misc.py`.
- Do not create a layer because it might be useful later. Add an abstraction
  when there is a real boundary or a second implementation.
- Keep public interfaces small. Internal details stay internal until another
  package genuinely needs them.
- Keep dependency direction obvious. Shared contracts sit below producers and
  consumers, not beside application-specific behavior.

For the simulator specifically:

- the simulation engine remains usable without a server, database or browser;
- browser/API code is an adapter around the core, never a dependency of it;
- hidden simulated truth and sensor observations remain separate paths;
- stochastic behavior must be reproducible from explicit seeds;
- new physics/biology fidelity should arrive behind narrow contracts rather
  than spreading engine-specific concepts through the world model.

## Python style

Ruff formatting is the source of truth. Do not hand-format around it.

The Python baseline is:

- Python 3.14+;
- Ruff formatting and linting;
- strict mypy;
- pytest;
- explicit types at package and architectural boundaries.

Avoid broad `Any`, untyped dictionaries and `type: ignore` as escape
hatches. When an ignore is unavoidable, keep it local and make the reason
obvious from the surrounding code or test.

Prefer straightforward code over dense transformations. Small duplication is
often cheaper than a premature generic abstraction.

### Name the numbers that carry meaning

A number that encodes a modelling assumption, a rate, a threshold, a range, a
tolerance or a unit conversion gets a name that says what it is. That is
where a reader looks to understand the model, and where a later change
happens without hunting for every copy.

- Use an UPPER_CASE constant, annotated `Final`, next to the code that owns
  it. Its comment gives the unit and what it controls.
- When several modules of one model share parameters, keep them in that
  model's `parameters.py`. `greenhouse_sim/biology/tomato/simple/parameters.py`
  is the example.
- A value a scenario should be able to change belongs in its configuration,
  not in a constant.
- Literals remain fine for arithmetic structure: `0`, `1`, `-1`, `2` for
  halves and midpoints, `100` for percentages, exponents and indices. They
  are also fine in tests, where the literal is the expected value.

`scripts/check_named_constants.py` enforces this for the packages' source. It
runs as a pre-commit hook on staged files and through the test suite in CI. It
treats a number as named when it is assigned to an UPPER_CASE or `Final` name,
is a class field's default, is passed as a keyword argument or is a
parameter's default. It cannot judge whether a keyword or a field is the
right home for a value, so review still applies.

In the viewer, Biome's `noMagicNumbers` rule enforces the same convention,
with test files exempt as well.

## TypeScript style (viewer)

The browser viewer in `greenhouse_sim/web` follows the same intent with its
own tools ([decision 0010](decisions/0010-check-the-viewer-with-biome-vitest-and-playwright.md)):

- Biome is the source of truth for formatting and linting, configured in
  `biome.json` at the repository root: two-space indent, 100-character
  lines, double quotes, the recommended rules, and `noMagicNumbers`.
- TypeScript is strict, with unchecked index access and exact optional
  properties also checked. Avoid `any` and non-null assertions as escape
  hatches, as with `Any` and `type: ignore` in Python.
- Data arriving from outside the viewer, such as an API response, is checked
  at runtime before it is trusted.
- Biome's accessibility rules take Three.js elements in the canvas, such as
  `<group onClick>`, for page elements. Ignore such a finding on its line,
  saying so; the rules still apply to the page around the canvas.
- Vitest covers behaviour at the narrowest useful level. A Playwright smoke
  test runs the built viewer against the real simulator API in Chromium.

## Tests

Test behavior at the narrowest useful level.

- Unit tests cover deterministic domain behavior and invariants.
- Characterization tests protect behavior across structural refactors.
- Contract/conformance tests protect package boundaries.
- Statistical tests validate stochastic behavior by distributions, not exact
  samples, except where deterministic seeds are intentionally part of the API.
- Visual regression tests protect the renderer's QA page: screenshots are
  compared in CI's pinned container
  ([decision 0014](decisions/0014-compare-screenshots-in-a-pinned-container-in-ci.md)).
- Slow external/network/CFD tests must be marked `slow` or kept outside the
  default fast loop.
- The renderer's performance is a local, non-blocking benchmark
  (`npm run bench` in the viewer), recorded with the machine it ran on
  ([decision 0015](decisions/0015-batch-repeated-shapes-and-benchmark-on-a-graphics-card.md)).

A test should make the failure understandable. Avoid broad end-to-end tests when
a smaller test can explain the broken contract.

## Local checks

After installing the development requirements and hooks:

```bash
pre-commit run --all-files
python scripts/check.py --fast
```

Before requesting review or merging a non-trivial change:

```bash
python scripts/check.py
```

The same canonical command is used by CI so local and remote checks do not
quietly drift apart.

For a change to the viewer, from `greenhouse_sim/web`, run the steps CI runs
in its `viewer checks` job:

```bash
npm ci
npm run lint && npm run typecheck && npm test && npm run build
PYTHON=python npm run e2e   # needs greenhouse-sim installed for that python
```
