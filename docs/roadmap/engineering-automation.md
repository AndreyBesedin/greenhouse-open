# AI-assisted engineering workflow roadmap

**Status:** Proposal, no automation enabled by this document. **Purpose:** improve delivery speed without sacrificing correctness. This process roadmap complements existing technical-debt plans.

## E1: Independent reviews and safe merge (first)

- [ ] Inventory and retain existing CI, DCO, risk checks, branch rules and Copilot reviews.
- [ ] Add independent Codex (or equivalent) review on PR creation and updates, reporting PASS / BLOCK / NEEDS_HUMAN / UNAVAILABLE, severity, file/line evidence, and tested head SHA.
- [ ] Introduce deterministic risk floor: protected core, public contracts, CI/security, dependencies, cross-package changes and size; LLM may escalate but never downgrade it.
- [ ] Pilot advisory-only review and validate false positives and false negatives.
- [ ] Enable auto-merge for explicit low-risk allowlisted changes only if all required deterministic checks pass, independent reviewer PASS applies to latest SHA, no blockers remain, and repository author/permission policy permits it.
- [ ] Fail closed for missing/stale reviews, workflow failures and ambiguous risk. Human approval for core science, architecture, public APIs, security and external contributors.
- [ ] Add an emergency disable switch and audit log.

**Acceptance:** failing CI, protected path, stale verdict or blocker prevents auto-merge; harmless allowlisted PR can pass.

## E2: Small and stacked PRs

- [ ] Default to one coherent, independently reversible change per PR; multiple commits are fine.
- [ ] Prefer stacked PRs for interface → implementation → integration → validation, each with its own base and CI.
- [ ] Evaluate Graphite against native GitHub stacks before adopting new tooling.
- [ ] Require clear PR description, risk, tests, roadmap links, and stack dependencies; retain existing size soft limits.

## E3: Slack engineering control room

- [ ] Separate CI/PR activity channel from daily engineering digest channel.
- [ ] Parent message per PR; replies in same thread for implementation agent, reviewer, CI, blockers, fixes, merge outcome.
- [ ] Include GitHub links, SHA, severity and action required; avoid noisy success messages.
- [ ] Store Slack credentials in secrets; use least privilege. Never execute fork PR code in a privileged notification workflow.
- [ ] Use Slack bot API and persist PR→thread_ts mapping for reliable replies; incoming webhook alone may not return a thread timestamp.
- [ ] Make event handling idempotent and escape untrusted PR titles/descriptions.
- [ ] Daily digest: merges, blocked PRs, failed checks, unresolved findings, QA trends.

**Acceptance:** one thread per PR, no duplicate events, actionable links, no secret leaks.

## E4: QA and architectural audits

- [ ] Keep fast PR checks; schedule comprehensive deterministic replay, randomized seeds, numerical invariants, long scenarios and golden fixtures nightly.
- [ ] Weekly audit of import boundaries, duplication, module growth, stale docs and test gaps; create prioritized issues rather than mass auto-refactors.
- [ ] Log reproducible scenario, seed, SHA and artifact for each failure.
- [ ] Sample auto-merged PRs for missed defects.

## E5: Longer-term parallel development

- [ ] Consolidate short shared agent instructions; encode testable architecture rules as tests.
- [ ] Measure lead time, human attention, rework, escaped defects and auto-merge quality.
- [ ] Version shared data contracts and fixtures; downstream consumers must not import simulator internals.
- [ ] Run cross-repository contract tests once interfaces stabilize.

## Proposed implementation PR stack

1. Risk matrix + structured review schema.
2. Advisory independent reviewer.
3. Safe, narrowly allowlisted merge gate.
4. Slack PR threads and security checks.
5. Daily digest + nightly QA.
6. Weekly architecture audit + metrics.
7. Optional stacked-PR tooling and cross-repo contracts.

**Manual setup needed:** reviewer provider credentials, Slack app/channel permissions, and GitHub branch rules. Keep private project/business details out of public repositories.
