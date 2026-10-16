# Engineering workflow: review, gates and automation

**Status:** revised 2026-10-17. Proposed on 2026-10-12 for after P09; by
2026-10-17 half of it had been done by other work, Dependabot (decisions
0033 and 0034), the [repository audit](../audits/2026-10-13-repository-audit.md)
and the Codex review, and the rest is re-planned below. **Purpose:** spend
the maintainer's review time where it matters, without letting correctness
depend on an AI verdict. Part of the [simulator roadmap](README.md). Its
identifiers (E1.1, …) track process work apart from the simulator's project
steps.

## Where the workflow stands

Measured on 2026-10-17, at the merge of #179 (`80d017c`). The first
measurement, on 2026-10-12 at #121, is in brackets where it differs.

- **Codex reviews every pull request** since #159 (2026-10-14), as a bot
  with its own identity, reading `AGENTS.md` as its rubric. On the 13 pull
  requests it commented on (#160–#178) it left 33 findings, 5 of them P1.
  19 were answered and their threads resolved (#164, #170, #177, #178); 14,
  on nine pull requests, were merged with their threads neither answered
  nor resolved. Of the 15 findings the maintainer's agent judged this week
  (#170, #177, #178), 15 were right; one found a hole in a fix whose tests
  passed (#178). Copilot has reviewed no pull request. [No bot reviewed.]
- **The `main` ruleset requires nine checks** since 2026-10-13: the
  repository, viewer and visual checks, the four browser lanes, the sign-off
  check and the risk gate. It does not require conversations to be resolved,
  although the [review policy](../engineering.md#solo-developer-review-policy)
  says it does, and the 14 unanswered threads above merged under it. The
  admin role bypasses it. Auto-merge is on, for Dependabot. [No check
  required; auto-merge off.]
- **The risk gate flags 70 of the last 100 merged pull requests**
  (#78–#179, 2026-10-08 to 2026-10-17), by line count on 40, a sensitive
  file on 38, file count on 24, kept simulation data on 14, CI on 13, the
  protocol on 6, several packages on 5. The 30 it clears are documents,
  tests, QA scenes and three Dependabot updates. [74 of 100.] The gate's
  lists were brought up to date by #170: `scripts/`, the paths truth leaves
  by, the kept simulation data, and the tick parsed as a rendered task item.
  It still runs the pull request's own copy of its script.
- **Dependabot keeps the dependencies current** (decisions 0033, 0034): a
  minor or patch update that changes no code merges by itself once the
  checks pass; two have (#157, #172). The rest wait for the maintainer's
  approval, which the gate takes as the acknowledgement.
- **Every pull request is still opened under the maintainer's account,**
  the agents' included. An agent's commits carry a `Co-Authored-By`
  trailer, which is the only record of who wrote what.
- **Architecture rules are tests:** `tests/test_dependencies.py`,
  the named-numbers check, `tests/test_publishable.py`, the sensor-truth
  boundary test, and [decision 0011](../decisions/0011-the-public-api-is-the-top-level-modules-contracts-and-scene.md).
  `AGENTS.md` (#159, #164) gives every assistant the same rubric, and
  `.claude/skills/address-review/` (#177) the procedure for answering a
  review.
- **A periodic audit exists:** the [repository audit of 2026-10-13](../audits/2026-10-13-repository-audit.md),
  indexed in [`docs/audits/`](../audits/README.md). Its W7 did the first half
  of E1.3 and its W8 schedules the season-long tests nightly on `main`.

## Direction

- **The deterministic floor decides; an AI verdict may raise the risk,
  never lower it, and is never enough on its own.** The reviewer reads
  diffs written by others, and a diff can tell it to answer PASS.
- **Fail closed.** A missing, stale or unavailable verdict, a failed
  workflow or an ambiguous risk blocks the automatic path; a person can
  still merge.
- **Everything a merge depends on is a required check on the head commit,**
  and GitHub's native auto-merge does the merging. No custom merge bot.
- **Measure before automating.** The reviewer stays advisory until its
  catches, misses and false alarms on this repository are counted.
- **Findings are recorded in the repository**
  ([decision 0001](../decisions/0001-keep-roadmap-and-decisions-in-the-repository.md)).
- **Built for the team that exists:** one maintainer and the agents they
  run.

## Steps

| Step | Change | Status |
| --- | --- | --- |
| E1.1 | Require the checks, and resolved conversations | Checks done 2026-10-13; resolution planned |
| E1.2 | Run the risk gate from the base branch | Planned |
| E1.3 | Extend the floor to what configures checks and dependencies | Half done (#170); rest planned |
| E1.4 | Keep "low risk" apart from "reviewed" | Deferred with E3 |
| E1.5 | Decide the agents' identity | Decided below: the maintainer's |
| E2.1 | An advisory reviewer | Done otherwise: Codex, since #159 |
| E2.2 | A reading guide for flagged pull requests | Planned, as a line in `AGENTS.md` |
| E2.3 | Try the reviewer on known escaped defects | Superseded by its live record |
| E2.4 | An advisory period, counted | Started below |
| E3.1 | Auto-merge for a narrow allowlist | Done for Dependabot (0033, 0034); the maintainer's own deferred |
| E3.2 | Record the policy | Done for Dependabot |
| E4.1 | Name a pull request's place in its stack | Planned |
| E5.1 | Nightly QA from P09's reference scenario | Folded into the audit's W8 |
| E5.2 | A periodic structural audit | Done: 2026-10-13 |

## E1: Harden the gates that exist

- **E1.1** Done for the checks. Left: the ruleset's "require conversation
  resolution", a setting made by hand. It makes the review policy's rule,
  that every review conversation is resolved or acknowledged, one GitHub
  enforces rather than one the 14 merged threads above show it does not.
- **E1.2** The gate takes its script from the base branch and classifies
  the pull request's diff with it, so a change to the gate is judged by the
  gate it changes. #170 changed the gate's lists and was judged by its own
  copy; its description said so, which is the manual version of this step.
- **E1.3** Done by #170 for `scripts/`, the paths truth leaves the simulator
  by and uploads come in, and the kept simulation data. Left: the test,
  coverage and lint configuration (`vite.config.ts`, `playwright.config.ts`,
  `biome.json`), the viewer's `package.json` as a dependency change, and the
  public API of decision 0011. `tests/test_pr_risk.py` covers each.
- **E1.4** Only auto-merge of the maintainer's own pull requests needs the
  gate to say "low risk" apart from "acknowledged". Deferred with E3.
- **E1.5** Decided: the agents the maintainer runs act as the maintainer,
  and "maintainer" in the review policy includes them. Their commits carry a
  `Co-Authored-By` trailer. A GitHub App of their own waits for a reason to
  tell their pull requests apart, such as a collaborator or E3 for the
  maintainer's pull requests. Nothing automatic acts with the maintainer's
  token: Dependabot's merges run on the workflow's.

**Acceptance:** a pull request that edits the risk script is judged by
`main`'s copy and flagged; a pull request with an unresolved conversation
cannot be merged except by the admin bypass; a change to `vite.config.ts`
is flagged.

## E2: The advisory reviewer, counted

Codex is the advisory reviewer. It posts findings as review comments, not a
check run with a verdict: a verdict only matters once a merge depends on
it, which is E3, deferred.

- **E2.2** For a pull request the gate flags, the reviewer opens with a
  reading guide: what is mechanical, what changes behaviour, where a person
  should look first. One paragraph in `AGENTS.md` asks Codex for it; whether
  it is useful shows in the count below.
- **E2.4** The count. Every Codex thread gets an answer: done, with the
  commit; deferred, with where; or declined, with the evidence. The
  judgement is recorded here, one row a pull request, as the pull requests
  are answered.

| Pull request | Findings | Right | Wrong | Acted on | Note |
| --- | --- | --- | --- | --- | --- |
| #170 | 5 | 5 | 0 | 5 | the risk gate's lists; a rename seen by its destination only |
| #177 | 9 | 9 | 0 | 9 | the address-review skill; forks, pagination, frozen audits |
| #178 | 1 | 1 | 0 | 1 | a flaky pass would have exited 0 and dropped its trace |
| #160–#168, #175 | 18 | not judged | | 4 | merged before this count began; #164's four answered |

**Acceptance:** no pull request merges with a Codex thread unanswered; the
table grows with each; after a month the right, wrong and acted-on columns
say whether E3 for the maintainer's pull requests is worth building.

## E3: Auto-merge, narrowly

Done for Dependabot: `scripts/dependabot_auto_merge.py` lets a minor or
patch update that changes no code merge by itself once the required checks
pass, and anything else waits for the maintainer's approval of its latest
commit, which the gate takes as the acknowledgement (decisions 0033, 0034).
The checks are required on the head commit and GitHub merges, as the
direction asks.

Auto-merge for the maintainer's own pull requests is deferred. The
measurement says why: the gate flags 70 of 100, and the 30 it clears are
documents the maintainer reads anyway, tests and QA scenes. The time goes on
the 70, where E2.2's reading guide helps and auto-merge does not. If E2.4's
count justifies it, the plan stands as proposed: an eligibility check that
passes only when the base is `main`, the floor gives no reason, the reviewer
passed this head commit, the author is on an allowlist read from the base
branch and the change lies within allowlisted paths; and a decision records
it. Fail closed: a flaky test blocks a merge, and is fixed (#178 moved the
traces that slowed the chromium lane to the retry).

## E4: Small and stacked pull requests

Already the practice. **E4.1** The pull request template asks for the pull
request's place in its stack and the one it builds on. The clean-up for
stacked reviews is in the project's clean-up document
(`docs/roadmap/p03-cleanup.md` for P03). Stacking tools are not planned.

## E5: Scheduled QA and audits

- **E5.1** The audit's W8 runs the season-long tests nightly on `main`. The
  QA part, deterministic replay against kept results, randomised seeds and
  the full browser suite, joins that schedule once it exists, each failure
  recording its scenario, seed, commit and artifacts.
- **E5.2** Done: the repository audit of 2026-10-13, and `docs/audits/` for
  the next. Import boundaries need no audit: `tests/test_dependencies.py`
  checks them on every pull request.

## Deferred

- **Auto-merge for the maintainer's pull requests, E1.4 and a verdict
  check,** until E2.4's count justifies them.
- **A GitHub App for the agents,** until a collaborator or E3 needs their
  pull requests told apart.
- **Slack.** GitHub's own Slack app, if wanted; no custom bot.
- **Delivery metrics** start as E2.4's count.
- **Trust tiers for collaborators,** until there is a collaborator.
- **Contract tests against downstream applications** belong in their
  repositories.

## Contributor trust and merge authorization

Auto-merge is an explicit privilege, never a consequence of passing CI or
receiving an AI PASS.

| Pull request's origin | Low risk | Medium or high risk |
| --- | --- | --- |
| Dependabot, a minor or patch update changing no code | Merges once the required checks pass (0033) | The maintainer's approval of its latest commit (0034) |
| The maintainer, or an agent acting as the maintainer | Deferred: eligible after all gates, once E2.4 justifies it | The maintainer's review and tick |
| A trusted collaborator allowlisted for autonomous merge (none today) | Eligible after all gates | The maintainer's approval |
| Any other contributor, forks included | The maintainer's approval | The maintainer's approval |

- Never trust labels, descriptions (the manual-review tick included),
  comments, branch names or author-supplied workflow metadata as proof of
  authorization. The gate reads the tick, but only after the floor has
  spoken, and the tick never makes a pull request low risk.
- The merge gate validates the authenticated author, the risk floor, the
  current head commit, CI, the reviewer's verdict where one is required and
  the protected branch's state at merge time.

## Order of work

1. By hand: the ruleset requires conversation resolution (E1.1).
2. One pull request: E1.2, the rest of E1.3 and E4.1.
3. `AGENTS.md`: the reading guide (E2.2); and the count (E2.4) kept here
   as pull requests are answered.
4. E5.1 with the audit's W8.
5. E3 for the maintainer's pull requests only if E2.4's count justifies it.
