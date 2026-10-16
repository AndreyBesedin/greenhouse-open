# GitHub CLI calls for a review

All calls use `gh`, already authenticated as the user. `{owner}/{repo}` is filled in
by `gh api` from the current checkout.

## Read the PR

```bash
gh pr view <n> --json number,title,state,headRefName,baseRefName,url,body,author,isDraft,mergeable,mergeStateStatus,autoMergeRequest
```

`mergeable` and `mergeStateStatus` read `UNKNOWN` for a few seconds after a push while
GitHub recomputes them; ask again. A conflicting PR runs no workflows, so a description
edit does not re-run a gate until the branch is rebased.

## Read the review

```bash
# Review summaries (bots put their overview here); state is APPROVED, CHANGES_REQUESTED, COMMENTED
gh api repos/{owner}/{repo}/pulls/<n>/reviews --paginate

# Inline comments: id, in_reply_to_id, user.login, path, line, body
gh api repos/{owner}/{repo}/pulls/<n>/comments --paginate

# Conversation comments on the PR itself
gh api repos/{owner}/{repo}/issues/<n>/comments --paginate

# Threads with their resolution state (GraphQL; the REST comments carry no isResolved)
gh api graphql -f query='query{repository(owner:"<owner>",name:"<repo>"){pullRequest(number:<n>){reviewThreads(first:100){nodes{id isResolved isOutdated comments(first:1){nodes{databaseId author{login} body}}}}}}}'
```

Pipe the JSON through `python3 -c` to print one block per comment: id, reply-to, author,
path, line, body. Read the full body; the first line is a badge or a title.

## Answer

```bash
# Reply in an inline thread (the id is the thread's first comment)
gh api -X POST repos/{owner}/{repo}/pulls/<n>/comments/<comment id>/replies -f body="..."

# React on a comment (content: +1, -1, laugh, confused, heart, hooray, rocket, eyes)
gh api -X POST repos/{owner}/{repo}/pulls/comments/<comment id>/reactions -f content=+1

# Comment on the PR conversation
gh pr comment <n> --body "..."

# Resolve a thread (needs the GraphQL thread id from the query above)
gh api graphql -f query='mutation{resolveReviewThread(input:{threadId:"<thread id>"}){thread{isResolved}}}'
```

Write long bodies to a file in the scratchpad and pass `--body-file`, or `-F body=@file`
for `gh api`, so shell quoting does not eat backticks.

## Update the description

```bash
gh pr edit <n> --body-file <scratchpad>/pr<n>_body.md
```

Start from the current body (`gh pr view <n> --json body --jq .body`), keep the
repository's template sections and checklist, and edit the facts that changed.

## Verify after the push

```bash
gh pr checks <n> --watch --fail-fast   # blocks until the checks finish
gh pr checks <n>                        # a snapshot
gh run view <run id> --log-failed       # why a check failed
```
