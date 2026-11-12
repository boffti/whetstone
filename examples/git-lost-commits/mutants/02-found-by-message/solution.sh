#!/usr/bin/env bash
# Misconception: the lost commit can be found by its message.
set -euo pipefail

git branch rescue "$(git log -g --format='%H %s' main | awk '/Cap night surcharge/ { print $1 }' | head -n 1)"
base=$(git merge-base main rescue)
git cherry-pick "$base..rescue"
