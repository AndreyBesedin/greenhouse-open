---
name: address-review
description: Work through the review of a pull request end to end - read every review comment (human, Copilot, Codex, other bots), judge which findings are right, fix the ones that are, verify with tests, push, reply on every thread, resolve what was fixed, update the PR description and report back. Use this whenever the user asks to check, address, respond to, handle, answer or "go through" review comments or review feedback on a PR, to "see what the reviewer/Codex/Copilot said", or to fix "what makes sense" from a review, even if they only give a PR number. Also use it when the user pastes review comments and asks whether they are valid.
---

# Address a review

The user wants a reviewed PR moved forward without doing the triage themselves. The
deliverable is three things: the right fixes pushed, every thread answered, and a short
report that says what was accepted, what was not and why, and what is left for them to do.

Reviews mix real defects, plausible-sounding mistakes, and style preferences. Both
failure modes cost the user: fixing a wrong finding damages the code and teaches the
bot nothing; dismissing a right one leaves a hole they trusted you to close. So the
heart of this skill is judging each finding on evidence, not on who wrote it or how
confident it sounds.

## 1. Gather the whole review

Read `references/github-cli.md` for the exact commands. Collect, for the PR:

- the PR's title, body, branch, base, author, merge state (`mergeable`, `mergeStateStatus`);
- reviews and their bodies (bot summaries often live here);
- inline review comments, with `in_reply_to_id`, `path`, `line`, and whether the
  thread is already resolved. A thread you answered in an earlier session needs
  no second reply unless a comment newer than yours arrived in it;
- issue comments on the PR (humans often write there, not inline).

Note who wrote each item, with their `author_association`. A maintainer's request,
an OWNER, MEMBER or COLLABORATOR as the risk gate reads it, is a decision unless it
rests on a factual mistake. Anyone can review a public repository's PR, so another
human's comment is a hypothesis, like a bot's finding, and is judged the same way.

Check out the PR (`gh pr checkout <n>`, which also fetches a fork's branch, where a
same-named branch of origin would mislead `git checkout`) and read the files the
comments point at, with their callers, not just the quoted lines. Read `AGENTS.md`,
`CONTRIBUTING.md` and `docs/engineering.md` before changing anything: the review
process, the risk gate and the commit rules are all there.

## 2. Judge each finding

For every comment decide one of: **fix now**, **fix elsewhere** (another PR, the
project's clean-up doc, a follow-up issue), **decline**. Write the verdict down
before you start editing; it becomes the report.

How to judge:

- **Reproduce the claim when it is cheap.** A reviewer saying "git reports only the
  destination of a rename" is settled by a scratch repository in thirty seconds. Run
  the failing input, read the library's behaviour, check the version. Reproduction
  turns "plausible" into "confirmed" or "wrong".
- **Check it against the repository's own policy.** If the finding cites a rule
  (`AGENTS.md`, a decision record, `docs/engineering.md`), read the rule. A finding
  that enforces a stated policy is nearly always right; one that invents a policy is
  not.
- **Weigh the fix against the threat model.** A self-review gate in a one-developer
  repository guards against accidents, not adversaries; a fix is worth it when the
  accident is plausible (the gate's own error output pasted into the description),
  not when it needs a hostile author.
- **Mind scope.** A correct finding whose fix touches files the PR does not own, or
  needs a design decision, goes to "fix elsewhere" with a note, not into this PR.
  A PR solves one coherent problem (`AGENTS.md`, section 8).
- **Prefer the smaller remedy.** The reviewer's proposed remedy is a suggestion; the
  finding is what matters. Often one flag, one list entry or one regex does it.
- **Style comments** follow `docs/engineering.md`, not the reviewer's taste. Decline
  politely when they conflict.

Do not fix a finding you could not confirm and could not refute either: say so in
the reply and the report, and let the user decide.

## 3. Fix, with tests that prove it

- Apply the repository's conventions from the start: early exits over nesting,
  named constants for grouped exclusions with a comment saying why, assumptions
  about another tool's output stated and checked where cheap.
- Every bug fix gets a regression test that fails on the old code. Prove it: stash
  the implementation (`git stash push -u -- <impl files>`, `-u` so a new file goes
  too), run the tests, pop. Report which tests failed before and pass after.
- When the PR changes something the PR itself exercises, such as the risk gate or
  a CI script, run the branch's version on the live inputs before pushing: the
  actual description (`gh pr view <n> --json body --jq .body`, the raw text rather
  than its JSON), the actual diff. The gate on
  #170 rejected a real tick because its own description quoted `<!--` in inline
  code; the unit tests passed and the live body would have caught it.
- Run the checks that cover what you changed: formatter, linter, type checker, the
  tests of every package touched. A Markdown-only change is covered too: the root
  `pytest` holds every document to its citations and publishability (#177's first
  push failed on a placeholder path). Run `uv run check --fast` when the
  change spans packages or touches shared code; when you skip it (a scripts-only
  change, say) because of its runtime, say so explicitly in the report and push
  with `--no-verify` only then.
- If the branch is behind its base, check `mergeable` before rebasing. A clean,
  behind branch can stay as it is; rebasing changes the diff the user reviewed.

## 4. Commit and push

- Conventional Commits (decision 0002) and a DCO sign-off (`git commit -s`), as
  `CONTRIBUTING.md` requires. Add the attribution trailer the session asks for.
- The commit body should say which review the fixes answer and, per finding, what
  changed and why. The reviewer and future readers will read it from `git blame`.
- Push to the PR branch. Then watch the checks (`gh pr checks <n> --watch`) and
  report their state; do not report success before they finish, and quote failures.

## 5. Answer every thread, then the description

Replies, commit messages and the description are the project's public
record: they say what changed, why and how it was checked, for any reader
of the project, and leave out the plans, events, deadlines and requests of
whoever asked for the work (decision 0044). The report in step 6 is where
the user hears about their own plans.

- One reply per thread. Fixed: what changed, in which commit, and which test covers
  it. Deferred: where it went (clean-up doc, issue, PR). Declined: the evidence,
  briefly and without defensiveness. Sign the reply with the agent's name, such as
  "— Claude", so the maintainer's own words and the agent's stay distinguishable
  on the PR.
- Resolve the threads you fixed. Leave declined and deferred threads open: the
  user decides those, and an open thread is the reminder. The review policy
  asks for every conversation to be resolved or acknowledged
  (`docs/engineering.md`); the `main` ruleset requires it only once a second
  person can merge (decision 0038).
- Bots that ask for a reaction get one: thumbs up when the finding was acted on,
  thumbs down when it was wrong. It is the only feedback they receive.
- Update the PR description so it describes the branch as it now is: changed-list,
  test counts, verification. Keep the template's sections and checklist. If the
  risk gate holds the PR and the user ticked "I manually reviewed the complete
  diff" before your push, untick it: the diff they reviewed is no longer the diff.
  It is their box to re-tick after reading the new commit, and silently keeping it
  ticked makes the gate pass on a review that did not happen.
- Saving the description starts a new risk-gate run (`pr-risk.yml` runs on
  `edited`), so look at the checks again after the edit and report that state,
  not the one you watched before it.

## 6. Report

Lead with what the user must do (re-tick, merge, decide a deferred item). If you
cleared their manual-review tick, the first sentence says so and says that the page
they have open still shows it ticked; a gate failing after "I ticked it" is otherwise
a puzzle for them. Then a table: finding, verdict, what was done, where. Then the
verification you ran and anything you skipped. Keep claims to what you verified; CI
still running is "still running", not "passing".

## Where deferred findings go

Findings on a project's stacked PRs that are left for later go into that project's
clean-up doc under `docs/roadmap/`, as `docs/roadmap/p03-cleanup.md` did for P03, under
a heading for the PR, on the reviewed branch, and merge up the stack. The clean-up runs as one PR once the
project's steps are merged. A finding about the repository as a whole goes to a
follow-up issue or the roadmap, not into an audit document: an audit records one
commit and is not edited once its work begins (`docs/audits/README.md`).
