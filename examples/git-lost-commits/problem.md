You work on `courier-fees`, the service that prices about 300,000 deliveries a day. This morning you meant to drop two scratch commits with `git reset --hard HEAD~2`, but you were on `main`, not your scratch branch. It dropped two finished commits: a night surcharge, and the cap the finance team asked for. Nobody pushed them anywhere.

Since then you kept working on `main` as if nothing happened. `sandbox/` is your clone, just as it is now. Try things there; it's yours to break. Then write the commands in `solution.sh`: the tests run it on fresh copies of the repo, including ones where you did other things after the reset.

## Stage 1

Make a branch named `rescue` that points at the newest lost commit: where `main` was just before the reset. Don't move `main`, and leave the working tree clean.

The tests' copies differ from yours: other commit messages, more commits lost, and other work after the reset, such as a teammate's branch merged in. All you know is that one reset on `main` did the damage, and that `main` hasn't been reset since.

## Stage 2

Now put the lost commits back on `main`, on top of everything done since, in their original order:

- Keep every commit made on `main` since the reset.
- History stays linear: no merge commits.
- Leave `rescue` where stage 1 put it: it's the record of what was lost.
- End on `main`, with a clean working tree.
