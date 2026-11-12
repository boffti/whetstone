## Where git remembers

A commit isn't deleted when a branch stops pointing at it. `git reset --hard HEAD~2` only moves `main` back two commits; the two commits stay in the repository, unreachable, until garbage collection removes them, by default after 30 days. The question is how to find them again.

Git keeps a **reflog** for every branch and for `HEAD`: a local diary of where each one pointed, newest first. Every commit, reset, merge and rebase that moves `main` adds a line.

```
$ git reflog show main --format='%gd %gs'
main@{0} merge hotfix: Fast-forward
main@{1} reset: moving to HEAD~1
main@{2} commit: Retry failed webhook deliveries
main@{3} commit: Sign webhook payloads
```

`main@{n}` names the commit `main` pointed at *n* moves ago, and works anywhere a commit does: `git branch keep 'main@{2}'`. Read the entries as "after this move, `main` was here". So the entry just below the reset is where `main` was *before* it.

Two shortcuts look right and break:

- **`ORIG_HEAD`** is where `HEAD` was before the last reset, merge or rebase, whichever came last. A merge after the accident overwrites it.
- **`HEAD@{1}`** is the previous position of `HEAD`, not of `main`. Any commit or checkout since the accident moves it.

Searching the log for the lost commit's message works on your clone, and only there. In a script, find the move, not the message.

## Putting commits back

`git cherry-pick A..B` replays every commit reachable from `B` but not from `A`, oldest first, on top of the current branch. Each replayed commit is a new commit with the same change and message. That's what keeps history linear, unlike `git merge`, which adds a merge commit when the branches have diverged.

`git merge-base main rescue` gives the last commit the two branches share. Here that's the commit the reset moved `main` to, so the range from it to `rescue` is exactly what was lost.

## Subgoals

1. **Find the move.** Read `main`'s reflog and find the reset.
2. **Name the commit before it.** Turn that entry's position into a `main@{n}` and branch from it.
3. **Pick the range.** Work out the shared base, then replay base..`rescue` onto `main`.
4. **Check the result.** `git log --oneline --graph main` shows the order and that there's no merge.

## In a script

`set -euo pipefail` stops at the first failing command. Inside `$( )`, a pipeline whose last command exits early (`grep -m1`, `head`) can make an earlier command fail with SIGPIPE on a long reflog. A filter that reads all its input avoids that.
