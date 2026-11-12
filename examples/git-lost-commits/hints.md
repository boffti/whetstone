Stage 1: `main` no longer points at the lost commits, but git remembers every place `main` has pointed. Where is that diary, and which line in it is the accident?

Stage 2: you want the lost commits' changes on top of `main`, as normal commits. Which command copies commits onto the current branch, and which range of commits is exactly the lost ones?

---

Stage 1: **find the move**, then **name the commit before it**. `main`'s reflog lists its moves newest first, and `main@{n}` is where it was *n* moves ago. The entry just below the reset is where `main` was before the reset. `ORIG_HEAD` and `HEAD@{1}` only work when nothing happened after the reset.

Stage 2: **pick the range**. `A..B` means "reachable from B, not from A". The shared base of `main` and `rescue` is where the reset left `main`.

---

Stage 1: `git reflog show main --format='%gs'` prints one move per line, the newest first. The first `reset: moving to` line, at line *k*, is `main@{k-1}`, so the commit before it is `main@{k}`. `awk` can print a line number (`NR`).

Stage 2: `git merge-base main rescue` gives the base; `git cherry-pick <base>..rescue` replays the lost commits, oldest first.

---

Stage 1:

```bash
n=$(git reflog show --format='%gs' main | awk '...')   # the line number of the first reset
git branch rescue "main@{$n}"
```

Stage 2:

```bash
base=$(git merge-base main rescue)
git cherry-pick ...
```
