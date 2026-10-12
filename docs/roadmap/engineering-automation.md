# AI-assisted engineering workflow roadmap

**Status:** proposal, scheduled after P09. Nothing in this document is
enabled yet. **Purpose:** spend the maintainer's review time where it
matters, without letting correctness depend on an AI verdict. Part of the
[simulator roadmap](README.md). Its identifiers (E1.1, …) track process work
separately from the simulator's project steps; it complements the technical
clean-up plans, such as the [frontend maintenance](frontend-maintenance.md)
and the test and CI time work recorded in the roadmap's index.

## Where the workflow stands

Measured on 2026-10-12, at the merge of #121.

- **No automated reviewer runs.** None of the pull requests sampled between
  #21 and #121 has a review from Copilot or any other bot, although the
  [review policy](../engineering.md#solo-developer-review-policy) describes
  Copilot reviewing each one.
- **No check is required to merge.** The `main protection` ruleset requires
  a pull request but no status check, gives the admin role an "always"
  bypass, and does not require conversations to be resolved, which the
  review policy says it should. Auto-merge is off for the repository.
- **The risk gate is already a deterministic floor.**
  [`scripts/check_pr_risk.py`](../../scripts/check_pr_risk.py) flags more
  than 500 code lines or 15 code files, several publishable packages, the
  protocol, `.github/`, package metadata and a list of sensitive files.
  Two weaknesses: `pr-risk.yml` runs the pull request's own copy of the
  script, so a change can rewrite the gate that judges it; and a small
  change to `scripts/check.py`, the viewer's coverage floor in
  `vite.config.ts` or its `package.json` passes as normal.
- **The gate flags most pull requests.** Run over the last 100 merged pull
  requests (#21–#121), it asks for the manual review on 74. Of the other 26,
  six are design documents, which the maintainer reviews anyway, and most of
  the rest are core-science features this plan sends to a person in any
  case. About ten test-only or QA pull requests are left. Auto-merge alone
  would therefore save little: review time goes on the large pull requests,
  and a reviewer that helps read them is worth more.
- **Every pull request is opened under the maintainer's account,** including
  those written by coding agents, which act with the maintainer's
  credentials and so carry the admin bypass.
- **Small and stacked pull requests are already the practice**
  ([change discipline](../engineering.md#change-discipline)).
- **Architecture rules are already tests:** `tests/test_dependencies.py`
  (what each package may import), the named-numbers check,
  `tests/test_publishable.py`, and
  [decision 0011](../decisions/0011-the-public-api-is-the-top-level-modules-contracts-and-scene.md)
  for what downstream applications may use.

## Direction

- **The deterministic floor decides; an AI verdict may raise the risk,
  never lower it, and is never enough on its own.** The reviewer reads
  diffs written by others, and a diff can tell it to answer PASS.
- **Fail closed.** A missing, stale or unavailable verdict, a failed
  workflow or an ambiguous risk blocks the automatic path; a person can
  still merge.
- **Everything a merge depends on is a required check on the head commit,**
  and GitHub's native auto-merge does the merging. A new push gets new
  checks, so no verdict outlives the commit it judged. No custom merge bot.
- **Measure before automating.** The reviewer stays advisory until its
  catches, misses and false alarms on this repository are counted.
- **Findings are recorded in the repository**
  ([decision 0001](../decisions/0001-keep-roadmap-and-decisions-in-the-repository.md)),
  in roadmap documents, rather than as issues.
- **Built for the team that exists:** one maintainer and the agents they
  run. What only a larger team needs waits for one.

## Steps

| Step | Change | Status |
| --- | --- | --- |
| E1.1 | Require the checks, and resolved conversations | Planned |
| E1.2 | Run the risk gate from the base branch | Planned |
| E1.3 | Extend the floor to what configures checks and dependencies | Planned |
| E1.4 | Keep "low risk" apart from "reviewed" | Planned |
| E1.5 | Decide the agents' identity | Planned |
| E2.1 | An advisory reviewer, as a check on the head commit | Planned |
| E2.2 | A reading guide for flagged pull requests | Planned |
| E2.3 | Try the reviewer on known escaped defects | Planned |
| E2.4 | An advisory period, counted | Planned |
| E3.1 | Auto-merge for a narrow allowlist, if E2.4 justifies it | Planned |
| E3.2 | Record the policy | Planned |
| E4.1 | Name a pull request's place in its stack | Planned |
| E5.1 | Nightly QA from P09's reference scenario | Planned |
| E5.2 | A periodic structural audit | Planned |

## E1: Harden the gates that exist

- **E1.1** The ruleset requires the checks that run on every pull request:
  repository checks, viewer checks, visual checks, the sign-off check and
  the risk gate. The CFD workflow runs only when its paths change, so it
  cannot be required. Conversations must be resolved. The admin bypass
  stays, for the maintainer's own merges.
- **E1.2** The risk gate takes its script from the base branch and
  classifies the pull request's diff with it, so a change to the gate is
  judged by the gate it changes.
- **E1.3** The floor also flags `scripts/` (the gate and the check suite),
  the test, coverage and lint configuration (`vite.config.ts`,
  `playwright.config.ts`, `biome.json`, `pyproject.toml`'s tool sections),
  the viewer's `package.json` as a dependency change, and the public API of
  decision 0011. `tests/test_pr_risk.py` covers each new category.
- **E1.4** The gate reports its classification on its own: a pull request
  is *low risk* only when the floor gives no reason. The "I manually
  reviewed the complete diff" tick lives in the description, which the
  author edits: it satisfies the manual review for a person's merge, and
  never makes a pull request low risk.
- **E1.5** Either agents get their own identity, a GitHub App without the
  admin bypass, so that their pull requests can be told apart; or this
  document and the review policy say plainly that "maintainer" includes the
  agents the maintainer runs. Either way, nothing automatic acts with the
  maintainer's token.

**Acceptance:** a pull request that edits the risk script is judged by
`main`'s copy and flagged; one whose CI fails cannot be merged except by the
admin bypass; a ticked description does not make a flagged pull request low
risk.

## E2: An advisory reviewer

- **E2.1** A workflow on `pull_request` (never `pull_request_target`) runs
  an independent reviewer, preferably a different model from the agent that
  wrote the change, and posts a check run on the head commit: a verdict of
  PASS, BLOCK, NEEDS_HUMAN or UNAVAILABLE, and each finding's severity, file
  and line. Its rubric is
  [`.github/copilot-instructions.md`](../../.github/copilot-instructions.md),
  shared rather than duplicated. It reads the diff and never runs the pull
  request's code. Its credential is a secret, so pull requests from forks
  are reviewed only when the maintainer asks. Its token can write checks
  and comments, nothing else.
- **E2.2** For a pull request the gate flags, the reviewer also writes a
  reading guide: what is mechanical, what changes behaviour, and where a
  person should look first. This is where most review time goes.
- **E2.3** Before it is trusted, the reviewer is run on pull requests with a
  known outcome: #109, which left four viewer panels ignoring the cloud
  override (found and fixed in #118), and #22, which let a failed bind be
  masked by an `AttributeError` (FE-AUDIT.6, fixed in #114); and as many
  clean pull requests, for false alarms. The results are recorded here.
- **E2.4** A few weeks advisory only, counting what it catches, misses and
  raises falsely, against what review and later fixes find.

**Acceptance:** the verdict belongs to the head commit and a push replaces
it; UNAVAILABLE never reads as PASS; E2.3's results are recorded.

## E3: Auto-merge, narrowly

Only if E2.4's numbers justify it.

- **E3.1** Auto-merge is enabled for the repository, and an eligibility
  check is required. It passes only when the base is `main` (inside a stack,
  auto-merge would merge into the pull request below), the floor gives no
  reason (E1.4), the reviewer passed this head commit, the author is on an
  allowlist read from the base branch, the change lies within allowlisted
  paths (tests and QA scenarios to begin with), and a repository variable
  that switches automatic merging off is unset. Turning auto-merge off in
  the repository's settings stops it outright.
- **E3.2** The review policy in `docs/engineering.md` is updated, and a
  decision recorded. The pull request's timeline, with its checks, is the
  audit log. Auto-merged pull requests are sampled regularly for missed
  defects.

Failing closed makes flaky tests block merges: the browser suite's weather
race failed a documentation-only pull request (#116) before #119 fixed it.
Flakes are fixed as they are found, and the test and CI time work decides
which checks a documentation-only change needs.

**Acceptance:** failing CI, a flagged path, a stale or missing verdict, a
ticked but flagged pull request, a base other than `main`, or an author
off the allowlist each prevents auto-merge, including when a label,
description, comment or branch name claims otherwise; a harmless
allowlisted pull request merges.

## E4: Small and stacked pull requests

Already the practice. One gap:

- **E4.1** The pull request template asks for the pull request's place in
  its stack and the one it builds on.

The size limits are crossed routinely (74 of the last 100). The change
discipline says to tighten the gate on actual review pain; E2's reading
guide and counts are the evidence to decide it with. Stacking tools are not
planned: the stack trouble seen so far (#104's conflicts) came from an
unrelated pull request landing first, which no tool prevents.

## E5: Scheduled QA and audits

- **E5.1** A nightly run grows from P09's reference scenario and release QA:
  deterministic replay against kept results, randomised seeds, long runs,
  and the full browser suite once pull requests run a subset of it. Each
  failure records its scenario, seed, commit and artifacts.
- **E5.2** A periodic audit of duplication, module growth, stale documents
  and test gaps, recorded in a roadmap document as the frontend audits are.
  Import boundaries need no audit: `tests/test_dependencies.py` checks them
  on every pull request.

## Deferred

- **Slack.** If wanted, GitHub's own Slack app posts one message per pull
  request with its activity threaded beneath it, and needs no secret in
  this public repository. A custom bot would need somewhere durable to keep
  each pull request's thread, which Actions does not have. A daily digest
  waits until someone other than the maintainer needs it.
- **Delivery metrics** (lead time, attention, rework) start as E2.4's
  counts.
- **Trust tiers for collaborators,** until there is a collaborator.
- **Contract tests against downstream applications** belong in their
  repositories, against the published packages and protocol.

## Contributor trust and merge authorization

Auto-merge is an explicit privilege, never a consequence of passing CI or
receiving an AI PASS.

| PR origin | Low risk | Medium/high risk |
| --- | --- | --- |
| Repository maintainer, explicitly allowlisted | Eligible after all gates | Human approval |
| Trusted collaborator, explicitly allowlisted for autonomous merge (none today) | Eligible after all gates | Human approval |
| Other collaborator or external contributor (including forks) | Maintainer approval | Maintainer approval |
| Automation or bot, with its own identity (E1.5) | Eligible only with verifiable maintainer-initiated authorization and explicit bot policy | Human approval |

- Today agents act as the maintainer (E1.5); the last row applies only once
  they have their own identity.
- GitHub write permission alone does not grant autonomous merge
  authorization.
- Keep a small, reviewed allowlist of identities authorized for low-risk
  autonomous merges, read from the base branch; changes to it require
  manual approval.
- Never trust pull request labels, descriptions (the manual-review tick
  included), comments, branch names or author-supplied workflow metadata as
  proof of authorization.
- The merge gate validates the authenticated pull request author, and
  trusted initiation where it applies, the risk floor, the current head
  commit, CI, the reviewer's verdict and the protected branch's state at
  merge time.
- An external contributor's pull request requires maintainer approval even
  when all tests and the AI review pass. No privileged bot bypasses this.
- Test contributor-role scenarios, including impersonation through metadata
  and pull requests from forks.

## Proposed implementation, after P09

1. E1: the settings, which are made by hand, and the gate's hardening.
2. E2.1–E2.3: the advisory reviewer, tried on known escaped defects.
3. E2.4: the advisory period.
4. E3, if the counts justify it.
5. E4.1 at any time; E5 with P09's release QA and the test and CI time
   work.

**Manual setup:** the ruleset, the reviewer's credential, and, under E1.5,
the agents' GitHub App. Keep private project and business details out of
this public repository.
