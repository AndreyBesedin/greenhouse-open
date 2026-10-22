# Commands for a release

All calls use `gh`, already authenticated as the user, from a checkout of the
repository. `{owner}/{repo}` is filled in by `gh api` from that checkout.

## Who may release

```bash
gh api user --jq .login                                  # who gh acts as
gh repo view --json owner --jq .owner.login              # the repository's owner
git fetch origin && git show origin/main:.github/release-managers   # the others
```

## Is main ready

```bash
git fetch origin --tags --prune
git describe --tags --abbrev=0 origin/main               # the last release's tag
git log --oneline "$(git describe --tags --abbrev=0 origin/main)"..origin/main
gh run list --branch main --workflow ci.yml --limit 1    # must be success
gh pr list --state open
```

## What merged since the last tag

```bash
since=$(git log -1 --format=%cI "$(git describe --tags --abbrev=0 origin/main)")
gh pr list --state merged --base main --limit 200 \
  --search "merged:>=${since%%T*}" --json number,title,mergedAt,mergeCommit
# Which of them has an entry: the changelog cites pull requests and issues by number.
sed -n '/^## Unreleased/,/^## [0-9]/p' CHANGELOG.md | grep -o '#[0-9]*' | sort -u
# An entry a later merge dropped: the changelog as that pull request merged it.
git show <merge-commit>:CHANGELOG.md | sed -n '/^## Unreleased/,/^## [0-9]/p'
```

## The release branch

```bash
git worktree add -b build/release-<version> \
  ../greenhouse-open-release-<version> origin/main
cd ../greenhouse-open-release-<version>
uv run setup
uv run release prepare <version>                         # --date YYYY-MM-DD for another day
git diff uv.lock                                         # three versions, nothing else
uv run check --fast
git commit -s -m "build: release <version>" -m "<body>"
git push -u origin build/release-<version>
gh pr create --base main --title "build: release <version>" --body-file <body.md>
```

## The video

```bash
uv run record-demo                                       # prints the recording, the cut, its first frame
```

A few frames through the cut, to check that each caption is on its view:

```bash
video=<the cut's path>
for at in 10 30 50 70; do
  ffmpeg -v error -y -ss "$at" -i "$video" -frames:v 1 -vf scale=640:-1 "<scratch>/frame-$at.png"
done
```

The URL the user's upload made, from the release pull request's comments. A
video dropped into a comment is written as its bare URL:

```bash
gh api "repos/{owner}/{repo}/issues/<n>/comments" --paginate \
  --jq '.[] | select(.user.login == "<owner or release manager>") | .body' \
  | grep -oE 'https://github\.com/user-attachments/assets/[0-9a-f-]+' | tail -1
```

Is it this recording:

```bash
curl -sL "<url>" | shasum -a 256
shasum -a 256 "<the cut's path>"
```

Then:

```bash
uv run release video "<url>"
git commit -s -am "docs(readme): the demo video recorded from <version>" -m "<body>"
git push
```

## Hand over

```bash
gh pr checks <n> --watch
gh pr view <n> --json body --jq .body                    # the manual-review box as it stands
```

## After the merge

```bash
gh pr view <n> --json mergeCommit --jq .mergeCommit.oid  # the merge commit
git fetch origin --tags
git switch --detach <the merge commit>
uv run release tag <n>                                   # the owner only: checks, tags, pushes
gh run list --workflow release.yml --limit 1             # the tag's push started it
gh run watch <run-id>
gh release view "v<version>" --json tagName,isLatest,url,body
gh run view <run-id> --log-failed                        # why a release was refused
gh run rerun <run-id>                                    # only for a failure on GitHub's side
git worktree remove ../greenhouse-open-release-<version>
git branch -D build/release-<version>
```
