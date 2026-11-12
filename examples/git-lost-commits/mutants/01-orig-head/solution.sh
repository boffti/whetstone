#!/usr/bin/env bash
# Misconception: ORIG_HEAD still points where main was before the reset.
set -euo pipefail

git branch rescue ORIG_HEAD
base=$(git merge-base main rescue)
git cherry-pick "$base..rescue"
